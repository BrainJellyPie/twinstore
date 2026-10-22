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
