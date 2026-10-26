"""Starting is observable before the background worker gets its first timeslice."""
import threading

import pytest
from fastapi.testclient import TestClient

from store_emulator.application import local_vlm
from store_emulator.application.hardware import HardwareProfile
from store_emulator.server.main import app


@pytest.mark.parametrize('previous', ['off', 'error'])
@pytest.mark.parametrize('trigger', ['direct', 'api'])
def test_start_reports_preparation_before_the_worker_runs(tmp_path, monkeypatch, previous, trigger):
    monkeypatch.delenv('TWINSTORE_LOCAL_VLM', raising=False)
    monkeypatch.setenv('PARASTORE_SETTINGS_DIR', str(tmp_path / 'settings'))
    mgr = local_vlm.LocalVLMManager(tmp_path, hardware=lambda: HardwareProfile(os='linux', arch='x64'))
    mgr._set(state=previous, message='old failure' if previous == 'error' else '', progress=.75)
    entered, release = threading.Event(), threading.Event()
    starts = []

    def worker():
        starts.append(True)
        entered.set()
        assert release.wait(5)
        mgr._set(state='ready', message='ready')

    monkeypatch.setattr(mgr, '_run', worker)
    monkeypatch.setattr(local_vlm, '_manager', [mgr])
    client = TestClient(app)
    try:
        status = client.post('/api/system/local-model/start').json() if trigger == 'api' else mgr.start().model_dump()
        assert entered.wait(2)
        assert mgr.busy()
        assert status['state'] == 'preparing'
        assert status['message'] != 'old failure' and status['progress'] is None
        assert client.get('/api/system/models').json()['local']['state'] == 'preparing'
        assert mgr.start().state == 'preparing' and starts == [True]
    finally:
        release.set()
        if mgr._thread is not None:
            mgr._thread.join(timeout=5)
    assert mgr.status().state == 'ready'


def test_a_pending_start_can_still_be_stopped_before_preparation(tmp_path, monkeypatch):
    monkeypatch.delenv('TWINSTORE_LOCAL_VLM', raising=False)
    mgr = local_vlm.LocalVLMManager(tmp_path)
    entered, release = threading.Event(), threading.Event()
    original = mgr._run

    def worker():
        entered.set()
        assert release.wait(5)
        original()

    monkeypatch.setattr(mgr, '_run', worker)
    monkeypatch.setattr(mgr, '_hardware', lambda: pytest.fail('Cancelled start must not probe hardware'))
    try:
        assert mgr.start().state == 'preparing'
        assert entered.wait(2)
        mgr.choose(False)
        mgr.stop()
        assert mgr.start().state == 'off'
    finally:
        mgr.stop()
        release.set()
        if mgr._thread is not None:
            mgr._thread.join(timeout=5)
    assert mgr.status().state == 'off' and mgr.chosen() is False
