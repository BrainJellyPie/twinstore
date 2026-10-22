"""File and port handling that has to hold on Windows: a file briefly in use there makes os.replace and open
fail with PermissionError, and SO_REUSEADDR lets a socket share a busy port."""

import errno
import socket
import sys
from pathlib import Path

import pytest

from store_emulator import launcher
from store_emulator.application.storage.io import read_json, write_json
from store_emulator.engine import files


def _flaky(monkeypatch: pytest.MonkeyPatch, name: str, failures: int) -> list[int]:
    calls: list[int] = []
    real = getattr(files.os, name) if name == "replace" else Path.read_text

    def flaky(*args: object, **kwargs: object) -> object:
        calls.append(1)
        if len(calls) <= failures:
            raise PermissionError(errno.EACCES, "The process cannot access the file because it is being used")
        return real(*args, **kwargs)  # type: ignore[operator]

    if name == "replace":
        monkeypatch.setattr(files.os, "replace", flaky)
    else:
        monkeypatch.setattr(Path, "read_text", flaky)
    monkeypatch.setattr(files.time, "sleep", lambda _s: None)
    return calls


def test_windows_rides_out_a_file_in_use(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(sys, "platform", "win32")
    path = tmp_path / "status.json"
    write_json(path, {"status": "running"})
    calls = _flaky(monkeypatch, "replace", failures=3)
    write_json(path, {"status": "done", "name": "한글 이름"})
    assert len(calls) == 4
    reads = _flaky(monkeypatch, "read_text", failures=2)
    assert read_json(path) == {"status": "done", "name": "한글 이름"}
    assert len(reads) == 3
    assert not list(tmp_path.glob("*.tmp-*"))


def test_elsewhere_a_permission_error_is_real(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(sys, "platform", "linux")
    calls = _flaky(monkeypatch, "replace", failures=1)
    with pytest.raises(PermissionError):
        write_json(tmp_path / "x.json", {"a": 1})
    assert len(calls) == 1


def test_windows_port_check_does_not_share_a_busy_port(monkeypatch: pytest.MonkeyPatch):
    busy = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    busy.bind(("127.0.0.1", 0))
    busy.listen()
    port = busy.getsockname()[1]
    options: list[int] = []
    real = socket.socket.setsockopt

    def spy(self: socket.socket, level: int, option: int, value: int) -> None:
        options.append(option)
        real(self, level, option, value)

    monkeypatch.setattr(socket.socket, "setsockopt", spy)
    monkeypatch.setattr(sys, "platform", "win32")
    try:
        assert launcher.free_port(port, "127.0.0.1") != port
        assert socket.SO_REUSEADDR not in options
    finally:
        busy.close()


def test_ui_files_get_their_web_types_whatever_the_registry_says():
    import mimetypes

    from store_emulator.server import main  # noqa: F401 — importing sets the types

    for name, kind in (("index-abc.js", "text/javascript"), ("x.mjs", "text/javascript"), ("index.css", "text/css"),
                       ("icon.svg", "image/svg+xml"), ("font.woff2", "font/woff2")):
        assert mimetypes.guess_type(name)[0] == kind


def test_remove_tree_waits_out_files_in_use_on_windows_and_clears_read_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import os
    import stat

    folder = tmp_path / "project"
    (folder / "runs").mkdir(parents=True)
    locked = folder / "runs" / "status.json"
    locked.write_text("{}", encoding="utf-8")
    readonly = folder / "image.png"
    readonly.write_bytes(b"x")
    os.chmod(readonly, stat.S_IREAD)
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(files.time, "sleep", lambda _s: None)
    real_unlink = os.unlink
    refusals = {"left": 2}

    def unlink(path: str, *args: object, **kwargs: object) -> None:
        if str(path).endswith("status.json") and refusals["left"] > 0:
            refusals["left"] -= 1
            raise PermissionError(errno.EACCES, "The process cannot access the file because it is being used")
        real_unlink(path, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(os, "unlink", unlink)
    files.remove_tree(folder)
    assert not folder.exists() and refusals["left"] == 0


def test_local_model_port_check_needs_a_port_it_can_listen_on():
    from store_emulator.application.local_vlm import _port_free  # pyright: ignore[reportPrivateUsage]

    taken = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    taken.bind(("127.0.0.1", 0))   # bound, not listening: connections are refused, but it cannot be used
    port = taken.getsockname()[1]
    try:
        assert _port_free(port) is False
    finally:
        taken.close()
    assert _port_free(port) is True


def test_hardware_probe_output_in_another_code_page_does_not_end_detection():
    from store_emulator.application.hardware import _run  # pyright: ignore[reportPrivateUsage]

    out = _run([sys.executable, "-c", "import sys; sys.stdout.buffer.write(b'NVIDIA \\xc7\\xd1\\xb1\\xdb GPU')"])
    assert out.startswith("NVIDIA ") and out.endswith(" GPU")
