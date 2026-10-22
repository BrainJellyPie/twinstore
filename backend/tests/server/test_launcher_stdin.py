"""The Python side of the app launcher stops when the launcher closes its stdin pipe. On Windows it must not
leave a read pending on that pipe: Windows serializes every operation on a synchronous pipe handle behind it,
which hung the first start of the server."""

import io
import signal
import sys

import pytest

from store_emulator import launcher


class _Stop(Exception):
    pass


def _stop_instead_of_exit(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    raised: list[int] = []

    def raise_signal(sig: int) -> None:
        raised.append(sig)
        raise _Stop

    monkeypatch.setattr(signal, "raise_signal", raise_signal)
    return raised


def test_windows_polls_the_pipe_instead_of_reading_it(monkeypatch: pytest.MonkeyPatch):
    raised = _stop_instead_of_exit(monkeypatch)
    polls = iter([False, False, True])
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(launcher, "_stdin_pipe_closed", lambda: next(polls), raising=False)
    monkeypatch.setattr(launcher.time, "sleep", lambda _s: None)

    class _NoRead(io.BytesIO):
        def read(self, size: int | None = -1) -> bytes:  # noqa: ARG002
            raise AssertionError("stdin must not be read on Windows")

    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(_NoRead()))
    with pytest.raises(_Stop):
        launcher._exit_when_stdin_closes()  # pyright: ignore[reportPrivateUsage]
    assert raised == [signal.SIGINT]


def test_elsewhere_end_of_input_stops(monkeypatch: pytest.MonkeyPatch):
    raised = _stop_instead_of_exit(monkeypatch)
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(b"")))
    with pytest.raises(_Stop):
        launcher._exit_when_stdin_closes()  # pyright: ignore[reportPrivateUsage]
    assert raised == [signal.SIGINT]
