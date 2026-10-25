"""CUDA companions must sit beside the executable, including wrapped upstream archives."""

import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import zipfile

import pytest

from store_emulator.application import local_vlm
from store_emulator.application.hardware import GPUInfo, recommend
from store_emulator.application.local_vlm import LocalVLMManager
from tests.engine.test_local_vlm import _hw


def _install(monkeypatch, root, *, os_name="linux", arch="x64", layout="separate", cached="fresh",
             server_bytes=b"offline server", libraries=None):
    monkeypatch.delenv("TWINSTORE_LLAMA_SERVER", raising=False)
    platform, extension = ("win", "zip") if os_name == "windows" else ("ubuntu", "tar.gz")
    main = f"llama-b11870-bin-{platform}-cuda-13.4-{arch}.{extension}"
    extra = f"cudart-{'llama' if os_name == 'windows' else 'llama-b11870'}-bin-{platform}-cuda-13.4-{arch}.{extension}"
    main_root = "" if layout == "flat" else ("llama-b11870/" if layout == "separate" else "llama-b11870/build/bin/")
    runtime_root = extra.removesuffix(f".{extension}") + "/" if layout == "separate" else ""
    server_name = "llama-server.exe" if os_name == "windows" else "llama-server"
    if libraries is None:
        names = (["cudart64_13.dll", "cublas64_13.dll", "cublasLt64_13.dll"] if os_name == "windows"
                 else ["libcudart.so.13", "libcublas.so.13", "libcublasLt.so.13"])
        libraries = {name: f"fixture:{name}".encode() for name in names}
    contents = {
        main: {main_root + server_name: server_bytes},
        extra: {runtime_root + name: body for name, body in libraries.items()},
    }
    release = {"tag_name": "b11870", "assets": [
        {"name": name, "browser_download_url": f"https://offline.invalid/{name}"} for name in contents]}
    hw = _hw(os=os_name, arch=arch, gpus=[GPUInfo(vendor="nvidia", name="Offline GPU", vram_gb=12, cuda="13.4")])
    plan = recommend(hw)
    requested, downloaded = [], []

    def metadata(request):
        requested.append(request.full_url)
        return io.BytesIO(json.dumps([release]).encode())

    manager = LocalVLMManager(root / "managed", opener=metadata, hardware=lambda: hw)
    target = manager.home / "bin" / "cuda"

    def archive(path):
        if os_name == "windows":
            with zipfile.ZipFile(path, "w") as out:
                for name, body in contents[path.name].items():
                    out.writestr(name, body)
        else:
            with tarfile.open(path, "w:gz") as out:
                for name, body in contents[path.name].items():
                    member = tarfile.TarInfo(name)
                    member.size, member.mode = len(body), 0o755 if name.endswith(server_name) else 0o644
                    out.addfile(member, io.BytesIO(body))

    def download(url, path, *, label):
        downloaded.append(path.name)
        archive(path)
        return path

    monkeypatch.setattr(manager, "_download", download)
    if cached != "fresh":
        target.mkdir(parents=True)
        for name in contents:
            path = target / name
            archive(path)
            local_vlm._safe_extract(path, target)
            path.unlink()
        (target / main_root / server_name).chmod(0o755)
        if cached == "marker":
            (target / local_vlm._COMPLETE).write_text(f"b11870 {main} {extra}\n")
        manager._may_download = False
    found = manager._runtime(hw, plan)
    return manager, hw, plan, found, requested, downloaded, libraries


@pytest.mark.parametrize("os_name", ["windows", "linux"])
@pytest.mark.parametrize("arch", ["x64", "arm64"])
@pytest.mark.parametrize("layout", ["separate", "flat", "runtime_flat"])
@pytest.mark.parametrize("cached", ["fresh", "marker", "legacy"])
def test_new_and_cached_runtime_libraries_are_beside_server(monkeypatch, tmp_path, os_name, arch, layout, cached):
    manager, hw, plan, server, requested, downloaded, libraries = _install(
        monkeypatch, tmp_path, os_name=os_name, arch=arch, layout=layout, cached=cached)
    for name, body in libraries.items():
        assert (server.parent / name).is_file(), f"{name} is outside the loader's executable directory"
        assert (server.parent / name).read_bytes() == body
        assert list((manager.home / "bin" / "cuda").rglob(name)) == [server.parent / name]
    assert len(downloaded) == (2 if cached == "fresh" else 0)
    assert len(requested) == int(cached == "fresh")
    assert manager._runtime(hw, plan) == server
    assert len(downloaded) == (2 if cached == "fresh" else 0)


@pytest.fixture(scope="module")
def linked_fixture(tmp_path_factory):
    if sys.platform != "linux" or shutil.which("cc") is None:
        pytest.skip("Linux ELF loader and a C compiler are required for this fixture")
    root = tmp_path_factory.mktemp("cuda-loader-fixture")
    library = root / "libcudart.so.13"
    source = root / "library.c"
    source.write_text("int twinstore_fixture_value(void) { return 42; }\n")
    subprocess.run(["cc", "-shared", "-fPIC", "-Wl,-soname,libcudart.so.13", str(source), "-o", str(library)], check=True)
    source = root / "server.c"
    source.write_text("int twinstore_fixture_value(void);\nint main(void) { return twinstore_fixture_value() == 42 ? 0 : 1; }\n")
    server = root / "llama-server"
    subprocess.run(["cc", str(source), "-L" + str(root), "-l:libcudart.so.13", "-Wl,-rpath,$ORIGIN", "-o", str(server)], check=True)
    return server.read_bytes(), library.read_bytes()


@pytest.mark.parametrize("cached", ["fresh", "marker"])
def test_linux_loader_finds_companion_without_external_library_paths(monkeypatch, tmp_path, linked_fixture, cached):
    executable, library = linked_fixture
    _, _, _, server, _, _, _ = _install(monkeypatch, tmp_path, cached=cached,
        server_bytes=executable, libraries={"libcudart.so.13": library})
    result = subprocess.run([str(server)], cwd=tmp_path, capture_output=True, text=True, timeout=5,
        env={key: value for key, value in os.environ.items() if key != "LD_LIBRARY_PATH"})
    assert result.returncode == 0, result.stderr
