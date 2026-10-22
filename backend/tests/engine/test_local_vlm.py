"""No API key: pick a local vision model for the hardware, fetch the matching llama.cpp build, serve it."""

import io
import json
import sys
import textwrap
import urllib.error
import urllib.request

import pytest
from fastapi.testclient import TestClient

from store_emulator.application import local_vlm, providers
from store_emulator.application.hardware import (
    GPUInfo,
    HardwareProfile,
    detect_hardware,
    downgrade,
    parse_nvidia_smi,
    recommend,
)
from store_emulator.application.local_vlm import LocalVLMManager, pick_runtime_assets
from store_emulator.domain.providers import ProviderKind

KEY_ENVS = ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "DASHSCOPE_API_KEY", "OPENROUTER_API_KEY")


@pytest.fixture
def no_keys(tmp_path, monkeypatch):
    monkeypatch.setenv("PARASTORE_SETTINGS_DIR", str(tmp_path / "settings"))
    for env in KEY_ENVS:
        monkeypatch.delenv(env, raising=False)
    return tmp_path


def _hw(**kw: object) -> HardwareProfile:
    base: dict[str, object] = {"os": "linux", "arch": "x64", "cpu": "test", "cores": 4, "threads": 8, "ram_gb": 16,
                               "ram_free_gb": 10, "gpus": []}
    return HardwareProfile.model_validate({**base, **kw})


def test_recommendation_follows_the_hardware():
    nv = GPUInfo(vendor="nvidia", name="RTX", vram_gb=12, cuda="12.8")
    big = recommend(_hw(gpus=[nv]))
    assert big.backend == "cuda" and big.model.key == "qwen3.5-9b" and big.gpu_layers > 0 and big.parallel == 4
    mid = recommend(_hw(gpus=[nv.model_copy(update={"vram_gb": 6})]))
    assert mid.backend == "cuda" and mid.model.key == "qwen3.5-4b"
    mac = recommend(_hw(os="macos", arch="arm64", ram_gb=16, gpus=[GPUInfo(vendor="apple", name="M2", vram_gb=16)]))
    assert mac.backend == "metal" and mac.model.key == "qwen3.5-4b"
    small_mac = recommend(_hw(os="macos", arch="arm64", ram_gb=8, gpus=[GPUInfo(vendor="apple", name="M1", vram_gb=8)]))
    assert small_mac.model.key == "qwen3.5-2b"
    amd = recommend(_hw(gpus=[GPUInfo(vendor="amd", name="RX", vram_gb=16)]))
    assert amd.backend == "vulkan" and amd.model.key == "qwen3.5-4b"          # capped below 9B on Vulkan
    igpu = recommend(_hw(gpus=[GPUInfo(vendor="intel", name="UHD", vram_gb=0)]))
    assert igpu.backend == "cpu" and igpu.gpu_layers == 0
    assert recommend(_hw(cores=16, ram_free_gb=24)).model.key == "qwen3.5-2b"
    assert recommend(_hw(cores=4, ram_free_gb=8)).model.key == "qwen3.5-0.8b"
    assert recommend(_hw(cores=2, ram_free_gb=8)).model.key == "lfm2.5-vl-450m"
    assert downgrade(big, _hw(gpus=[nv])).backend == "cpu"


def test_nvidia_smi_parsing_and_detection_never_raises():
    gpus = parse_nvidia_smi("NVIDIA GeForce RTX 4070, 12282\n", "| NVIDIA-SMI 560.35  Driver Version: 560.35  CUDA Version: 12.6 |")
    assert gpus == [GPUInfo(vendor="nvidia", name="NVIDIA GeForce RTX 4070", vram_gb=12.0, cuda="12.6")]
    hw = detect_hardware(run=lambda cmd: "")       # no tools at all
    assert hw.threads >= 1 and hw.cores >= 1
    assert recommend(hw).model.key                  # always some plan


RELEASE = [f"llama-b9001-bin-{s}" for s in (
    "ubuntu-x64.tar.gz", "ubuntu-arm64.tar.gz", "ubuntu-vulkan-x64.tar.gz", "ubuntu-cuda-12.8-x64.tar.gz",
    "ubuntu-cuda-13.4-x64.tar.gz", "macos-arm64.tar.gz", "macos-x64.tar.gz", "win-cpu-x64.zip", "win-vulkan-x64.zip",
    "win-cuda-12.4-x64.zip", "win-cuda-13.4-x64.zip")] + [
    "cudart-llama-b9001-bin-ubuntu-cuda-12.8-x64.tar.gz", "cudart-llama-b9001-bin-ubuntu-cuda-13.4-x64.tar.gz",
    "cudart-llama-bin-win-cuda-12.4-x64.zip", "cudart-llama-bin-win-cuda-13.4-x64.zip"]


def test_runtime_assets_match_os_gpu_and_driver():
    linux12 = pick_runtime_assets(RELEASE, os_name="linux", arch="x64", backend="cuda", cuda="12.9")
    assert linux12 == ["llama-b9001-bin-ubuntu-cuda-12.8-x64.tar.gz", "cudart-llama-b9001-bin-ubuntu-cuda-12.8-x64.tar.gz"]
    assert pick_runtime_assets(RELEASE, os_name="linux", arch="x64", backend="cuda", cuda="13.4")[0].endswith("cuda-13.4-x64.tar.gz")
    win = pick_runtime_assets(RELEASE, os_name="windows", arch="x64", backend="cuda", cuda="12.6")
    assert win == ["llama-b9001-bin-win-cuda-12.4-x64.zip", "cudart-llama-bin-win-cuda-12.4-x64.zip"]
    # A driver older than every CUDA build, or no Vulkan build for the arch: the CPU build.
    assert pick_runtime_assets(RELEASE, os_name="linux", arch="x64", backend="cuda", cuda="11.8") == ["llama-b9001-bin-ubuntu-x64.tar.gz"]
    assert pick_runtime_assets(RELEASE, os_name="linux", arch="arm64", backend="vulkan") == ["llama-b9001-bin-ubuntu-arm64.tar.gz"]
    assert pick_runtime_assets(RELEASE, os_name="macos", arch="arm64", backend="metal") == ["llama-b9001-bin-macos-arm64.tar.gz"]
    assert pick_runtime_assets(RELEASE, os_name="windows", arch="x64", backend="vulkan") == ["llama-b9001-bin-win-vulkan-x64.zip"]


FAKE_SERVER = textwrap.dedent('''\
    import sys, http.server
    port = int(sys.argv[sys.argv.index("--port") + 1])
    assert "--mmproj" in sys.argv and "-m" in sys.argv
    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200 if self.path == "/health" else 404); self.end_headers(); self.wfile.write(b'{"status":"ok"}')
        def log_message(self, *a): pass
    http.server.HTTPServer(("127.0.0.1", port), H).serve_forever()
''')


class _Resp(io.BytesIO):
    def __init__(self, data: bytes) -> None:
        super().__init__(data)
        self.headers = {"Content-Length": str(len(data))}
        self.status = 200


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX shebang script stands in for llama-server")
def test_manager_downloads_the_model_serves_it_and_points_the_provider_at_it(no_keys, monkeypatch):
    script = no_keys / "llama-server"
    script.write_text(f"#!{sys.executable}\n" + FAKE_SERVER)
    script.chmod(0o755)
    monkeypatch.setenv("TWINSTORE_LLAMA_SERVER", str(script))
    monkeypatch.delenv("TWINSTORE_LOCAL_VLM", raising=False)
    monkeypatch.setattr(local_vlm, "DEFAULT_PORT", local_vlm._free_port())  # pyright: ignore[reportPrivateUsage]  # not a llama.cpp server running here
    fetched: list[str] = []

    def opener(req: urllib.request.Request):   # downloads only; health checks go to the real server
        fetched.append(req.full_url)
        return _Resp(b"gguf-bytes")

    mgr = LocalVLMManager(no_keys / "local_vlm", opener=opener, hardware=lambda: _hw(cores=4, ram_free_gb=8))
    try:
        status = mgr.start(wait=True)
        assert status.state == "ready", status.message
        assert status.managed and status.plan is not None and status.plan.model.key == "qwen3.5-0.8b"
        assert [u.rsplit("/", 1)[-1] for u in fetched] == ["Qwen3.5-0.8B-Q4_K_M.gguf", "mmproj-F16.gguf"]
        assert all(u.startswith("https://huggingface.co/unsloth/Qwen3.5-0.8B-GGUF/resolve/main/") for u in fetched)
        llama = providers.provider_status(ProviderKind.LLAMACPP)
        assert llama.ready and llama.api_base == status.api_base
        assert providers.resolve_model("llamacpp:local").api_base == status.api_base
        # The models are kept: a second start downloads nothing.
        mgr.stop()
        fetched.clear()
        assert mgr.start(wait=True).state == "ready" and fetched == []
    finally:
        mgr.stop()


def test_turned_off_by_environment(no_keys, monkeypatch):
    monkeypatch.setenv("TWINSTORE_LOCAL_VLM", "off")
    mgr = LocalVLMManager(no_keys / "lv", hardware=lambda: _hw())
    assert mgr.start().state == "disabled"


@pytest.mark.parametrize("payload, advertised_size", [(b"partial", 100), (b"", 0), (b"too long", 3)])
def test_incomplete_model_download_is_not_cached_and_can_be_retried(tmp_path, payload, advertised_size):
    responses = [_Resp(payload), _Resp(b"complete-model")]
    responses[0].headers["Content-Length"] = str(advertised_size)
    mgr = LocalVLMManager(tmp_path, opener=lambda req: responses.pop(0))
    path = tmp_path / "models" / "test__model" / "model.gguf"

    with pytest.raises(RuntimeError, match="[Dd]ownload"):
        mgr._download_model("test/model", "model.gguf")

    assert not path.exists()
    # A short read is kept to be continued; nothing, or more than announced, is thrown away.
    assert path.with_name(path.name + ".part").exists() == (0 < len(payload) < advertised_size)
    assert mgr._download_model("test/model", "model.gguf").read_bytes() == b"complete-model"
    assert responses == []


def test_download_without_content_length_accepts_nonempty_response(tmp_path):
    response = _Resp(b"complete-model")
    response.headers.clear()
    mgr = LocalVLMManager(tmp_path, opener=lambda req: response)
    assert mgr._download_model("test/model", "model.gguf").read_bytes() == b"complete-model"


def test_failed_download_preserves_existing_file_and_removes_partial(tmp_path):
    class InterruptedResponse(_Resp):
        def read(self, size=-1):
            if self.tell():
                raise OSError("connection interrupted")
            return super().read(size)

    response = InterruptedResponse(b"partial")
    mgr = LocalVLMManager(tmp_path, opener=lambda req: response)
    path = tmp_path / "runtime.zip"
    path.write_bytes(b"previous-download")
    with pytest.raises(OSError, match="connection interrupted"):
        mgr._download("https://example.invalid/runtime.zip", path, label="runtime")
    assert path.read_bytes() == b"previous-download"
    assert not path.with_name(path.name + ".part").exists()


def test_model_setup_warns_without_any_key_and_not_with_one(no_keys, monkeypatch):
    from store_emulator.server.main import app

    monkeypatch.setenv("TWINSTORE_LOCAL_VLM", "off")
    monkeypatch.setattr(local_vlm, "_manager", [LocalVLMManager(no_keys / "lv", hardware=lambda: _hw())])
    client = TestClient(app)
    body = client.get("/api/system/models").json()
    assert body["cloud_providers"] == [] and "No API key is set" in body["warning"]
    assert body["plan"]["model"]["key"] == "qwen3.5-0.8b" and body["hardware"]["cores"] == 4
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-0000000000")
    body = client.get("/api/system/models").json()
    assert body["cloud_providers"] == ["Anthropic (Claude)"] and body["warning"] is None
    assert json.dumps(body).count("sk-ant") == 0


def _asset(name: str) -> dict[str, object]:
    return {"name": name, "browser_download_url": f"https://github.com/ggml-org/llama.cpp/releases/download/x/{name}"}


# As llama.cpp publishes them since its versioned releases: the newest ("latest") carries no binaries; numbered
# builds, marked as pre-releases, do.
_RELEASES: list[dict[str, object]] = [
    {"tag_name": "b11805", "draft": True, "prerelease": True, "assets": [_asset("llama-b11805-bin-win-cpu-x64.zip")]},
    {"tag_name": "v0.7.0", "draft": False, "prerelease": False, "assets": [_asset("nightly-tag.txt")]},
    {"tag_name": "b11804", "draft": False, "prerelease": True, "assets": [_asset(n) for n in (
        "llama-b11804-bin-win-cpu-x64.zip", "llama-b11804-bin-win-vulkan-x64.zip",
        "llama-b11804-bin-win-cuda-12.4-x64.zip", "llama-b11804-bin-win-cuda-13.4-x64.zip",
        "cudart-llama-bin-win-cuda-12.4-x64.zip", "cudart-llama-bin-win-cuda-13.4-x64.zip",
        "llama-b11804-bin-macos-arm64.tar.gz", "llama-b11804-bin-ubuntu-x64.tar.gz")]},
    {"tag_name": "b11803", "draft": False, "prerelease": True, "assets": [_asset("llama-b11803-bin-ubuntu-arm64.tar.gz")]},
]


def test_the_newest_release_with_a_build_for_this_machine_is_used():
    from store_emulator.application.local_vlm import pick_release

    win = pick_release(_RELEASES, os_name="windows", arch="x64", backend="cpu")
    assert win is not None and win[0] == "b11804" and win[1] == ["llama-b11804-bin-win-cpu-x64.zip"]
    assert win[2][win[1][0]].endswith("llama-b11804-bin-win-cpu-x64.zip")
    cuda = pick_release(_RELEASES, os_name="windows", arch="x64", backend="cuda", cuda="12.8")
    assert cuda is not None and cuda[1] == ["llama-b11804-bin-win-cuda-12.4-x64.zip", "cudart-llama-bin-win-cuda-12.4-x64.zip"]
    # A build only an older release has is found there.
    arm = pick_release(_RELEASES, os_name="linux", arch="arm64", backend="cpu")
    assert arm is not None and arm[0] == "b11803"
    assert pick_release(_RELEASES[:2], os_name="windows", arch="x64", backend="cpu") is None


def test_runtime_download_skips_a_release_without_binaries(tmp_path, monkeypatch):
    import tarfile

    monkeypatch.delenv("TWINSTORE_LLAMA_SERVER", raising=False)
    monkeypatch.setattr(local_vlm.shutil, "which", lambda _name: None)
    archive = io.BytesIO()
    with tarfile.open(fileobj=archive, mode="w:gz") as t:
        body = b"#!/bin/sh\n"
        info = tarfile.TarInfo("build/bin/llama-server")
        info.size = len(body)
        t.addfile(info, io.BytesIO(body))
    fetched: list[str] = []

    def opener(req: urllib.request.Request):
        fetched.append(req.full_url)
        if req.full_url == local_vlm.RELEASES_URL:
            return _Resp(json.dumps(_RELEASES).encode())
        return _Resp(archive.getvalue())

    mgr = LocalVLMManager(tmp_path / "lv", opener=opener, hardware=lambda: _hw(os="linux", arch="x64"))
    hw, plan = mgr.plan()
    server = mgr._runtime(hw, plan.model_copy(update={"backend": "cpu"}))  # pyright: ignore[reportPrivateUsage]
    assert server.name == "llama-server" and server.is_file()
    assert fetched == [local_vlm.RELEASES_URL, "https://github.com/ggml-org/llama.cpp/releases/download/x/llama-b11804-bin-ubuntu-x64.tar.gz"]
    assert mgr.status().runtime == "b11804 llama-b11804-bin-ubuntu-x64.tar.gz"


def test_a_half_installed_build_is_fetched_again_and_a_gpu_plan_without_a_gpu_build_drops_to_the_cpu(no_keys, monkeypatch):
    from store_emulator.application.hardware import downgrade

    home = no_keys / "local_vlm"
    leftover = home / "bin" / "cuda" / "build" / "bin"
    leftover.mkdir(parents=True)
    (leftover / "llama-server").write_text("")          # the cudart download never finished: no marker
    monkeypatch.setattr(local_vlm.shutil, "which", lambda name: None)
    releases = [{"tag_name": "b9001", "assets": [{"name": n, "browser_download_url": f"https://x/{n}"} for n in RELEASE]}]
    fetched: list[str] = []

    def opener(req: urllib.request.Request):
        fetched.append(req.full_url)
        return _Resp(json.dumps(releases).encode())

    mgr = LocalVLMManager(home, opener=opener, hardware=lambda: _hw(cores=4, ram_free_gb=8))
    gpu = _hw(cores=4, ram_free_gb=8)
    cuda_plan = local_vlm.recommend(gpu).model_copy(update={"backend": "cuda"})
    # An old driver: the newest releases have only the CPU build for it.
    monkeypatch.setattr(local_vlm, "pick_release", lambda *a, **k: ("b9001", ["llama-b9001-bin-ubuntu-x64.tar.gz"], {}))
    with pytest.raises(local_vlm._NoGpuBuild):  # pyright: ignore[reportPrivateUsage]
        mgr._runtime(gpu, cuda_plan)  # pyright: ignore[reportPrivateUsage]
    assert not (home / "bin" / "cuda").exists()          # the half-installed build is gone
    assert downgrade(cuda_plan, gpu).backend == "cpu"


def _offline(req: urllib.request.Request):
    raise urllib.error.URLError("no route to github.com")


def _old_build(root, files: dict[str, bytes]) -> None:
    """bin/<backend> as versions before 0.4.3 left it: unpacked archives (removed once unpacked), no .complete marker."""
    for name, body in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        if name.endswith("llama-server"):
            path.chmod(0o755)


@pytest.mark.parametrize(("backend", "files"), [
    ("cpu", {"build/bin/llama-server": b"#!/bin/sh\n", "build/bin/libggml-cpu.so": b"\x7fELF"}),
    ("vulkan", {"build/bin/llama-server": b"#!/bin/sh\n", "build/bin/libggml-vulkan.so": b"\x7fELF"}),
    ("cuda", {"build/bin/llama-server": b"#!/bin/sh\n", "build/bin/libggml-cuda.so": b"\x7fELF",
              "libcudart.so.12": b"\x7fELF", "libcublas.so.12": b"\x7fELF"}),
])
@pytest.mark.skipif(sys.platform == "win32", reason="checks the executable bit the old versions set")
def test_a_whole_build_from_before_the_marker_is_kept(no_keys, monkeypatch, backend, files):
    monkeypatch.delenv("TWINSTORE_LLAMA_SERVER", raising=False)
    monkeypatch.setattr(local_vlm.shutil, "which", lambda _name: None)
    home = no_keys / "local_vlm"
    _old_build(home / "bin" / backend, files)
    mgr = LocalVLMManager(home, opener=_offline, hardware=lambda: _hw())
    hw, plan = mgr.plan()
    server = mgr._runtime(hw, plan.model_copy(update={"backend": backend}))  # pyright: ignore[reportPrivateUsage]
    assert server == home / "bin" / backend / "build" / "bin" / "llama-server"
    assert {p.relative_to(home / "bin" / backend).as_posix() for p in (home / "bin" / backend).rglob("*") if p.is_file()} == set(files)


@pytest.mark.skipif(sys.platform == "win32", reason="checks the executable bit the old versions set")
def test_a_model_an_old_version_downloaded_starts_with_nothing_downloaded(no_keys, monkeypatch):
    monkeypatch.delenv("TWINSTORE_LLAMA_SERVER", raising=False)
    monkeypatch.delenv("TWINSTORE_LOCAL_VLM", raising=False)
    monkeypatch.setattr(local_vlm.shutil, "which", lambda _name: None)
    home = no_keys / "local_vlm"
    asked: list[str] = []

    def opener(req: urllib.request.Request):
        asked.append(req.full_url)
        raise urllib.error.URLError("offline")

    mgr = LocalVLMManager(home, opener=opener, hardware=lambda: _hw())
    _, plan = mgr.plan()
    _old_build(home / "bin" / plan.backend, {"build/bin/llama-server": b"#!/bin/sh\n", "build/bin/libggml.so": b"\x7fELF"})
    models = home / "models" / plan.model.repo.replace("/", "__")
    models.mkdir(parents=True)
    for name in (plan.model.file, plan.model.mmproj):
        (models / name).write_bytes(b"gguf")
    served: list[str] = []
    monkeypatch.setattr(mgr, "_answers", lambda port: False)
    monkeypatch.setattr(mgr, "_serve", lambda server, model, mmproj, plan: (
        served.append(server.name), mgr._set(state="ready", message="")))  # pyright: ignore[reportPrivateUsage]
    assert mgr.on_disk(plan)
    assert mgr.auto_start()                              # nobody chose it: only what is on this computer
    assert mgr._thread is not None  # pyright: ignore[reportPrivateUsage]
    mgr._thread.join(timeout=10)  # pyright: ignore[reportPrivateUsage]
    assert asked == [] and served == ["llama-server"] and mgr.status().state == "ready"


@pytest.mark.parametrize("leftover", [
    "llama-b9001-bin-ubuntu-x64.tar.gz",           # unpacking was cut short (the archive went once unpacked)
    "llama-b9001-bin-ubuntu-x64.tar.gz.part",      # the download was cut short
])
def test_an_old_build_left_mid_way_is_fetched_again(no_keys, monkeypatch, leftover):
    monkeypatch.delenv("TWINSTORE_LLAMA_SERVER", raising=False)
    monkeypatch.setattr(local_vlm.shutil, "which", lambda _name: None)
    home = no_keys / "local_vlm"
    _old_build(home / "bin" / "cpu", {"build/bin/llama-server": b"#!/bin/sh\n", leftover: b"\x1f\x8b"})
    mgr = LocalVLMManager(home, opener=_offline, hardware=lambda: _hw())
    hw, plan = mgr.plan()
    with pytest.raises(RuntimeError, match="could not reach GitHub"):
        mgr._runtime(hw, plan.model_copy(update={"backend": "cpu"}))  # pyright: ignore[reportPrivateUsage]
    assert not (home / "bin" / "cpu").exists()


def test_an_interrupted_download_continues_where_it_stopped(no_keys):
    data = bytes(range(256)) * 40
    ranges: list[str | None] = []

    class _Dropped(io.BytesIO):
        """Sends the first 3000 bytes, then the connection drops."""
        def __init__(self) -> None:
            super().__init__(data[:3000])
            self.headers = {"Content-Length": str(len(data))}
            self.status = 200

        def read(self, n: int = -1) -> bytes:
            chunk = super().read(n)
            if not chunk:
                raise OSError("connection reset")
            return chunk

    def opener(req: urllib.request.Request):
        ranges.append(req.get_header("Range"))
        if len(ranges) == 1:
            return _Dropped()
        start = int(str(req.get_header("Range")).removeprefix("bytes=").removesuffix("-"))
        resp = _Resp(data[start:])
        resp.status = 206
        return resp

    mgr = LocalVLMManager(no_keys / "local_vlm", opener=opener, hardware=lambda: _hw())
    target = no_keys / "model.gguf"
    with pytest.raises(OSError, match="connection reset"):
        mgr._download("https://x/model.gguf", target, label="model")  # pyright: ignore[reportPrivateUsage]
    assert (no_keys / "model.gguf.part").stat().st_size == 3000 and not target.exists()
    mgr._download("https://x/model.gguf", target, label="model")  # pyright: ignore[reportPrivateUsage]
    assert target.read_bytes() == data and not (no_keys / "model.gguf.part").exists()
    assert ranges == [None, "bytes=3000-"]


def test_only_a_llama_cpp_server_that_reads_images_is_taken_over(monkeypatch):
    answers: dict[str, object] = {}

    class _Open:
        @staticmethod
        def open(url: str, timeout: float = 0):
            if "props" not in answers:
                raise OSError("404")
            return _Resp(json.dumps(answers["props"]).encode())

    monkeypatch.setattr(local_vlm, "_DIRECT", _Open())
    base = "http://127.0.0.1:8081/v1"
    assert not local_vlm._serves_images(base)                    # pyright: ignore[reportPrivateUsage]  # another program
    answers["props"] = {"status": "ok"}
    assert not local_vlm._serves_images(base)                    # pyright: ignore[reportPrivateUsage]  # not llama.cpp
    answers["props"] = {"total_slots": 2, "modalities": {"vision": False}}
    assert not local_vlm._serves_images(base)                    # pyright: ignore[reportPrivateUsage]  # text only
    answers["props"] = {"total_slots": 2, "modalities": {"vision": True}}
    assert local_vlm._serves_images(base) and local_vlm._server_slots(base) == 2  # pyright: ignore[reportPrivateUsage]
    answers["props"] = {"total_slots": 1}
    assert local_vlm._serves_images(base)                        # pyright: ignore[reportPrivateUsage]  # older builds
