"""CUDA runtime companions must match the server's OS, architecture and version."""

import io
import json
import random
import tarfile
import zipfile

import pytest

from store_emulator.application import local_vlm
from store_emulator.application.hardware import GPUInfo, recommend
from store_emulator.application.local_vlm import LocalVLMManager, pick_runtime_assets
from tests.engine.test_local_vlm import _hw


# These CUDA 13.4 names occur together in the public b11870 release, checked 2026-10-25.
ASSETS = [
    "cudart-llama-b11870-bin-ubuntu-cuda-13.4-arm64.tar.gz",
    "cudart-llama-b11870-bin-ubuntu-cuda-13.4-x64.tar.gz",
    "cudart-llama-bin-win-cuda-13.4-arm64.zip",
    "cudart-llama-bin-win-cuda-13.4-x64.zip",
    "llama-b11870-bin-ubuntu-cuda-13.4-arm64.tar.gz",
    "llama-b11870-bin-ubuntu-cuda-13.4-x64.tar.gz",
    "llama-b11870-bin-win-cuda-13.4-arm64.zip",
    "llama-b11870-bin-win-cuda-13.4-x64.zip",
]


@pytest.mark.parametrize("os_name,platform,extension", [("windows", "win", "zip"), ("linux", "ubuntu", "tar.gz")])
@pytest.mark.parametrize("arch", ["x64", "arm64"])
@pytest.mark.parametrize("order", ["published", "reversed", "shuffled"])
@pytest.mark.parametrize("driver", ["13.4", "14.0"])
def test_release_asset_order_cannot_select_another_platform_runtime(os_name, platform, extension, arch, order, driver):
    names = list(ASSETS)
    if order == "reversed":
        names.reverse()
    elif order == "shuffled":
        random.Random(201).shuffle(names)
    selected = pick_runtime_assets(names, os_name=os_name, arch=arch, backend="cuda", cuda=driver)
    suffix = f"-bin-{platform}-cuda-13.4-{arch}.{extension}"
    assert len(selected) == 2 and all(name.endswith(suffix) for name in selected)
    assert not selected[0].startswith("cudart-") and selected[1].startswith("cudart-")


@pytest.mark.parametrize("os_name,platform,extension", [("windows", "win", "zip"), ("linux", "ubuntu", "tar.gz")])
@pytest.mark.parametrize("arch", ["x64", "arm64"])
def test_newer_cuda_without_its_companion_uses_an_older_complete_pair(os_name, platform, extension, arch):
    main = f"llama-b11870-bin-{platform}-cuda-12.4-{arch}.{extension}"
    companion = f"cudart-{main}"
    names = [name for name in ASSETS if not (name.startswith("cudart-") and f"-bin-{platform}-" in name)] + [main, companion]
    assert pick_runtime_assets(names, os_name=os_name, arch=arch, backend="cuda", cuda="13.4") == [main, companion]


@pytest.mark.parametrize("os_name,platform,extension,cpu", [
    ("windows", "win", "zip", "win-cpu"), ("linux", "ubuntu", "tar.gz", "ubuntu"),
])
@pytest.mark.parametrize("arch", ["x64", "arm64"])
@pytest.mark.parametrize("has_cpu", [False, True])
def test_missing_companions_never_produce_an_incomplete_gpu_install(os_name, platform, extension, cpu, arch, has_cpu):
    names = [name for name in ASSETS if not (name.startswith("cudart-") and f"-bin-{platform}-" in name)]
    fallback = f"llama-b11870-bin-{cpu}-{arch}.{extension}"
    if has_cpu:
        names.append(fallback)
    assert pick_runtime_assets(names, os_name=os_name, arch=arch, backend="cuda", cuda="13.4") == ([fallback] if has_cpu else [])


@pytest.mark.parametrize("os_name", ["windows", "linux"])
@pytest.mark.parametrize("cached_wrong_pair", [False, True])
def test_runtime_install_extracts_matching_libraries_and_reuses_complete_build(monkeypatch, tmp_path, os_name, cached_wrong_pair):
    monkeypatch.delenv("TWINSTORE_LLAMA_SERVER", raising=False)
    names = list(ASSETS if os_name == "windows" else reversed(ASSETS))
    release = {"tag_name": "b11870", "assets": [
        {"name": name, "browser_download_url": f"https://offline.invalid/{name}"} for name in names]}
    hw = _hw(os=os_name, gpus=[GPUInfo(vendor="nvidia", name="Offline GPU", vram_gb=12, cuda="13.4")])
    plan = recommend(hw)
    manager = LocalVLMManager(tmp_path / "local", opener=lambda _: io.BytesIO(json.dumps([release]).encode()), hardware=lambda: hw)
    if cached_wrong_pair:
        target = manager.home / "bin" / "cuda"
        target.mkdir(parents=True)
        windows = os_name == "windows"
        (target / ("llama-server.exe" if windows else "llama-server")).write_bytes(b"old server")
        (target / ("libcudart.so.13" if windows else "cudart64_13.dll")).write_bytes(b"wrong platform")
        native = "win" if windows else "ubuntu"
        foreign = "ubuntu" if windows else "win"
        main = next(name for name in names if name.startswith("llama-") and f"-bin-{native}-" in name and "-x64." in name)
        companion = next(name for name in names if name.startswith("cudart-") and f"-bin-{foreign}-" in name and "-x64." in name)
        (target / local_vlm._COMPLETE).write_text(f"b11870 {main} {companion}\n")
    downloaded = []

    def download(url, path, *, label):
        downloaded.append(path.name)
        windows = "-bin-win-" in path.name
        name = ("cudart64_13.dll" if windows else "libcudart.so.13") if path.name.startswith("cudart-") else (
            "llama-server.exe" if windows else "llama-server")
        content = b"offline runtime fixture"
        if windows:
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr(name, content)
        else:
            with tarfile.open(path, "w:gz") as archive:
                member = tarfile.TarInfo(name)
                member.size, member.mode = len(content), 0o755
                archive.addfile(member, io.BytesIO(content))
        return path

    monkeypatch.setattr(manager, "_download", download)
    server = manager._runtime(hw, plan)
    library = "cudart64_13.dll" if os_name == "windows" else "libcudart.so.13"
    foreign = "libcudart.so.13" if os_name == "windows" else "cudart64_13.dll"
    assert (server.parent / library).is_file() and not (server.parent / foreign).exists()
    assert len(downloaded) == 2 and all("-x64." in name for name in downloaded)
    marker = (server.parent / local_vlm._COMPLETE).read_text()
    assert all(name in marker for name in downloaded)
    assert manager._runtime(hw, plan) == server and len(downloaded) == 2
