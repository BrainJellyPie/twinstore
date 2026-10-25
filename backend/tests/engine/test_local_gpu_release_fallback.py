"""An incomplete new release must not hide a usable GPU build in recent releases."""

import io
import json
import tarfile

import pytest

from store_emulator.application import local_vlm
from store_emulator.application.hardware import GPUInfo, recommend
from store_emulator.application.local_vlm import LocalVLMManager, pick_release
from tests.engine.test_local_vlm import _asset, _hw


def _names(tag, os_name, backend, *, arch="x64", cuda="13.4"):
    platform, extension = ("win", "zip") if os_name == "windows" else ("ubuntu", "tar.gz")
    variant = f"cuda-{cuda}" if backend == "cuda" else backend
    platform = f"{platform}-{variant}" if backend != "cpu" or os_name == "windows" else platform
    main = f"llama-{tag}-bin-{platform}-{arch}.{extension}"
    return [main, f"cudart-{main}"] if backend == "cuda" else [main]


def _release(tag, names, **extra):
    return {"tag_name": tag, "assets": [_asset(name) for name in names], **extra}


@pytest.mark.parametrize("os_name", ["windows", "linux"])
@pytest.mark.parametrize("backend", ["cuda", "vulkan"])
@pytest.mark.parametrize("gap", ["missing", "foreign_arch"])
def test_new_cpu_release_does_not_hide_older_gpu(os_name, backend, gap):
    newest = _names("b11872", os_name, "cpu")
    if gap == "foreign_arch":
        newest += _names("b11872", os_name, backend, arch="arm64")
    wanted = _names("b11870", os_name, backend)
    releases = [
        _release("b11872", newest),
        _release("b11871", _names("b11871", os_name, backend), draft=True),
        _release("v0.7.0", []),
        _release("b11870", wanted, prerelease=True),
        _release("b11869", _names("b11869", os_name, backend)),
    ]
    selected = pick_release(releases, os_name=os_name, arch="x64", backend=backend, cuda="13.4")
    assert selected is not None and selected[:2] == ("b11870", wanted)
    assert all(selected[2][name].endswith(name) for name in wanted)


@pytest.mark.parametrize("os_name", ["windows", "linux"])
@pytest.mark.parametrize("gap", ["driver_too_old", "missing_companion"])
def test_incompatible_or_incomplete_cuda_release_keeps_older_gpu(os_name, gap):
    gpu = _names("b11871", os_name, "cuda", cuda="14.0" if gap == "driver_too_old" else "13.4")
    if gap == "missing_companion":
        gpu.pop()
    wanted = _names("b11870", os_name, "cuda", cuda="12.4")
    selected = pick_release([
        _release("b11871", _names("b11871", os_name, "cpu") + gpu),
        _release("b11870", wanted),
    ], os_name=os_name, arch="x64", backend="cuda", cuda="13.4")
    assert selected is not None and selected[:2] == ("b11870", wanted)


@pytest.mark.parametrize("os_name", ["windows", "linux"])
@pytest.mark.parametrize("backend", ["cuda", "vulkan"])
def test_complete_new_gpu_build_still_wins(os_name, backend):
    wanted = _names("b11871", os_name, backend)
    selected = pick_release([
        _release("b11871", _names("b11871", os_name, "cpu") + wanted),
        _release("b11870", _names("b11870", os_name, backend)),
    ], os_name=os_name, arch="x64", backend=backend, cuda="13.4")
    assert selected is not None and selected[:2] == ("b11871", wanted)


@pytest.mark.parametrize("os_name", ["windows", "linux"])
@pytest.mark.parametrize("backend", ["cuda", "vulkan"])
def test_no_usable_gpu_still_uses_newest_cpu_release(os_name, backend):
    wanted = _names("b11871", os_name, "cpu")
    releases = [
        _release("b11872", _names("b11872", os_name, backend), draft=True),
        _release("b11871", wanted + _names("b11871", os_name, backend, arch="arm64")),
        _release("b11870", _names("b11870", os_name, "cpu")),
    ]
    for requested in (backend, "cpu"):
        selected = pick_release(releases, os_name=os_name, arch="x64", backend=requested, cuda="13.4")
        assert selected is not None and selected[:2] == ("b11871", wanted)


@pytest.mark.parametrize("backend,vendor,model_key", [
    ("cuda", "nvidia", "qwen3.5-9b"), ("vulkan", "amd", "qwen3.5-4b"),
])
def test_startup_retains_gpu_and_model_when_latest_release_is_partial(monkeypatch, tmp_path, backend, vendor, model_key):
    monkeypatch.delenv("TWINSTORE_LLAMA_SERVER", raising=False)
    wanted = _names("b11870", "linux", backend)
    releases = [_release("b11871", _names("b11871", "linux", "cpu")), _release("b11870", wanted)]
    hw = _hw(gpus=[GPUInfo(vendor=vendor, name="Offline GPU", vram_gb=12, cuda="13.4")])
    original = recommend(hw)
    manager = LocalVLMManager(tmp_path, opener=lambda _: io.BytesIO(json.dumps(releases).encode()), hardware=lambda: hw)
    downloaded, models, served = [], [], []

    def download(url, path, *, label):
        downloaded.append(path.name)
        name = "libcudart.so.13" if path.name.startswith("cudart-") else "llama-server"
        body = b"offline archive fixture"
        with tarfile.open(path, "w:gz") as archive:
            member = tarfile.TarInfo(name)
            member.size, member.mode = len(body), 0o755
            archive.addfile(member, io.BytesIO(body))
        return path

    def download_model(repo, file):
        models.append((repo, file))
        return tmp_path / file

    def serve(server, model, mmproj, plan):
        served.append((server, model, mmproj, plan))
        manager._set(state="ready")

    monkeypatch.setattr(manager, "_answers", lambda _: False)
    monkeypatch.setattr(manager, "_download", download)
    monkeypatch.setattr(manager, "_download_model", download_model)
    monkeypatch.setattr(manager, "_serve", serve)
    manager._pipeline()
    status = manager.status()
    assert status.state == "ready", status.message
    assert status.plan == original and status.plan.model.key == model_key
    assert downloaded == wanted
    assert models == [(original.model.repo, file) for file in (original.model.file, original.model.mmproj)]
    assert len(served) == 1 and served[0][3] == original
    assert served[0][0].is_file() and "b11870" in status.runtime
    assert not (tmp_path / "bin" / "cpu").exists()
