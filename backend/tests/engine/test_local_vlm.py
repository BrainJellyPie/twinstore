"""No API key: pick a local vision model for the hardware, fetch the matching llama.cpp build, serve it."""

import io
import json
import sys
import textwrap
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
    assert not path.with_name(path.name + ".part").exists()
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
