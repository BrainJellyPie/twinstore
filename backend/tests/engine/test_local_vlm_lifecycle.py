"""Starting and stopping the local model must not leave work running after cancellation."""

import io
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from store_emulator.application import local_vlm
from store_emulator.application.hardware import HardwareProfile
from store_emulator.application.local_vlm import LocalVLMManager


@pytest.mark.parametrize("stage", ["hardware", "runtime", "download"])
def test_stop_cancels_preparation_before_a_server_is_started(tmp_path, monkeypatch, stage):
    entered = threading.Event()
    release = threading.Event()
    served: list[Path] = []

    def pause():
        entered.set()
        assert release.wait(5), "test did not release the worker"

    def hardware():
        if stage == "hardware":
            pause()
        return HardwareProfile(os="linux", arch="x64", cores=2, threads=2)

    def runtime(hw, plan):
        if stage == "runtime":
            pause()
        return tmp_path / "llama-server"

    class Response(io.BytesIO):
        headers = {"Content-Length": "5"}

        def read(self, size=-1):
            if stage == "download" and not self.tell():
                pause()
            return super().read(size)

    mgr = LocalVLMManager(tmp_path, hardware=hardware, opener=lambda req: Response(b"model"))
    monkeypatch.setattr(mgr, "_answers", lambda port: False)
    monkeypatch.setattr(mgr, "_runtime", runtime)
    monkeypatch.setattr(mgr, "_serve", lambda server, *args: served.append(server))
    try:
        mgr.start()
        assert entered.wait(5), "worker never reached the blocking stage"
        mgr.stop()
        assert mgr.status().state == "off"
    finally:
        release.set()
        if mgr._thread is not None:
            mgr._thread.join(timeout=5)

    assert mgr._thread is not None and not mgr._thread.is_alive()
    assert served == []
    assert mgr.status().state == "off"
    assert not list(tmp_path.rglob("*.part"))
    mgr.start(wait=True)
    assert served == [tmp_path / "llama-server"]


def test_stop_reaps_a_server_that_ignores_termination(tmp_path, monkeypatch):
    class Process:
        def __init__(self):
            self.returncode = None
            self.killed = False
            self.waits = 0

        def poll(self):
            return self.returncode

        def terminate(self):
            pass

        def kill(self):
            self.killed = True

        def wait(self, timeout=None):
            self.waits += 1
            if not self.killed:
                raise local_vlm.subprocess.TimeoutExpired("llama-server", timeout)
            self.returncode = -9
            return self.returncode

    mgr = LocalVLMManager(tmp_path)
    proc = Process()
    monkeypatch.setattr(mgr, "_proc", proc)
    mgr._set(state="ready", managed=True, api_base="http://127.0.0.1:8081/v1")
    mgr.stop()
    assert proc.killed and proc.waits == 2
    assert mgr.status().state == "off" and mgr.status().api_base is None


def test_stop_while_loading_never_marks_the_terminated_server_ready(tmp_path, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    configured: list[str] = []

    class Process:
        returncode = None

        def poll(self):
            return self.returncode

        def terminate(self):
            self.returncode = 0

        def wait(self, timeout=None):
            return self.returncode

    proc = Process()
    mgr = LocalVLMManager(tmp_path, hardware=lambda: HardwareProfile(os="linux", arch="x64"))

    def answers(port):
        if mgr._proc is None:
            return False
        entered.set()
        assert release.wait(5)
        return True

    from store_emulator.application import providers
    monkeypatch.setattr(mgr, "_answers", answers)
    monkeypatch.setattr(mgr, "_runtime", lambda *args: tmp_path / "llama-server")
    monkeypatch.setattr(mgr, "_download_model", lambda *args: tmp_path / "model.gguf")
    monkeypatch.setattr(local_vlm.subprocess, "Popen", lambda *args, **kwargs: proc)
    monkeypatch.setattr(providers, "use_local_server", configured.append)
    try:
        mgr.start()
        assert entered.wait(5)
        mgr.stop()
    finally:
        release.set()
        if mgr._thread is not None:
            mgr._thread.join(timeout=5)
    assert proc.poll() == 0 and mgr._proc is None
    assert mgr.status().state == "off" and not mgr.status().managed
    assert configured == []


def test_start_does_not_reuse_a_server_while_it_is_stopping(tmp_path, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    starts: list[bool] = []

    def terminate(proc):
        entered.set()
        assert release.wait(5)

    mgr = LocalVLMManager(tmp_path)
    monkeypatch.setattr(mgr, "_proc", object())
    monkeypatch.setattr(local_vlm, "_terminate", terminate)
    monkeypatch.setattr(mgr, "_run", lambda: starts.append(True))
    worker = threading.Thread(target=mgr.stop)
    worker.start()
    try:
        assert entered.wait(5)
        mgr.start(wait=True)
        assert starts == []
    finally:
        release.set()
        worker.join(timeout=5)
    mgr.start(wait=True)
    assert starts == [True]


def test_concurrent_start_requests_create_only_one_worker(tmp_path, monkeypatch):
    starting, release, finish, second_created = (threading.Event() for _ in range(4))
    workers: list[threading.Thread] = []

    class DelayedThread(threading.Thread):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            workers.append(self)
            if len(workers) > 1:
                second_created.set()

        def start(self):
            starting.set()
            assert release.wait(5)
            super().start()

    mgr = LocalVLMManager(tmp_path)
    monkeypatch.setattr(mgr, "_run", lambda: finish.wait(5))
    monkeypatch.setattr(local_vlm, "threading", SimpleNamespace(Thread=DelayedThread))
    first = threading.Thread(target=mgr.start)
    second = threading.Thread(target=mgr.start)
    first.start()
    try:
        assert starting.wait(5)
        second.start()
        second_created.wait(0.1)
        release.set()
        first.join(timeout=5)
        second.join(timeout=5)
        assert not first.is_alive() and not second.is_alive()
        assert len(workers) == 1
    finally:
        release.set()
        finish.set()
        first.join(timeout=5)
        if second.ident is not None:
            second.join(timeout=5)
        for worker in workers:
            worker.join(timeout=5)
