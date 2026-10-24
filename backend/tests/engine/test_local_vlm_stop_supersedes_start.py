"""A queued automatic or button Start must not revive a model after the user stops it."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

from store_emulator.application.local_vlm import LocalVLMManager


@pytest.mark.parametrize('automatic', [False, True])
@pytest.mark.parametrize('previous_choice', [None, True])
def test_stop_supersedes_a_start_waiting_after_its_choice_check(tmp_path, monkeypatch, automatic, previous_choice):
    from store_emulator.server.routes import system

    manager = LocalVLMManager(tmp_path)
    monkeypatch.delenv('TWINSTORE_LOCAL_VLM', raising=False)
    if previous_choice is not None:
        manager.choose(previous_choice)
    entered, release = Event(), Event()
    original = manager.start
    starts = []
    monkeypatch.setattr(manager, '_run', lambda: starts.append('worker'))
    monkeypatch.setattr(system, 'manager', lambda: manager)

    def delayed_start(**kwargs):
        entered.set()
        assert release.wait(5)
        return original(**kwargs)

    monkeypatch.setattr(manager, 'start', delayed_start)
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(manager.auto_start if automatic else system.start_local_model)
        try:
            assert entered.wait(5)
            stopped = system.stop_local_model()
            assert stopped.state == 'off' and manager.chosen() is False
        finally:
            release.set()
        result = pending.result(timeout=5)
    if manager._thread is not None:
        manager._thread.join(timeout=5)
    assert starts == [] and manager._cancel.is_set()
    if automatic:
        assert result is False
    else:
        assert result.state == 'off'

    # A later explicit Start is a new user choice and can run normally.
    monkeypatch.setattr(manager, 'start', original)
    system.start_local_model()
    manager._thread.join(timeout=5)
    assert starts == ['worker'] and manager.chosen() is True and not manager._cancel.is_set()
