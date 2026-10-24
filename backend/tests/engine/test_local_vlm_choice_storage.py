"""A failed preference write must not undo the user's local-model Start/Stop."""

import errno
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from store_emulator.application import local_vlm
from store_emulator.application.local_vlm import LocalVLMManager


def deny_choice_storage(monkeypatch, home, failure):
    if failure == 'mkdir':
        mkdir = Path.mkdir

        def denied(path, *args, **kwargs):
            if path == home:
                raise PermissionError(errno.EACCES, 'choice directory is read-only')
            return mkdir(path, *args, **kwargs)

        monkeypatch.setattr(Path, 'mkdir', denied)
    else:
        replace = local_vlm.replace_file

        def full(source, destination):
            if destination == home / 'choice.json':
                raise OSError(errno.ENOSPC, 'choice cannot be saved')
            return replace(source, destination)

        monkeypatch.setattr(local_vlm, 'replace_file', full)
        if failure == 'cleanup':
            unlink = Path.unlink

            def locked(path, *args, **kwargs):
                if path.parent == home and path.name.startswith('choice.json.'):
                    raise PermissionError(errno.EACCES, 'temporary file is locked')
                return unlink(path, *args, **kwargs)

            monkeypatch.setattr(Path, 'unlink', locked)


@pytest.mark.parametrize('use', [False, True])
@pytest.mark.parametrize('failure', ['mkdir', 'replace', 'cleanup'])
def test_failed_persistence_keeps_the_latest_choice_for_this_session(tmp_path, monkeypatch, use, failure):
    home = tmp_path / 'local'
    home.mkdir()
    choice = home / 'choice.json'
    choice.write_text(json.dumps({'use': not use}))
    manager = LocalVLMManager(home)
    assert manager.chosen() is not use
    deny_choice_storage(monkeypatch, home, failure)
    manager.choose(use)
    assert manager.chosen() is use
    # Failed persistence does not damage the previous preference. Only this session changes.
    assert LocalVLMManager(home).chosen() is not use
    starts = []
    monkeypatch.delenv('TWINSTORE_LOCAL_VLM', raising=False)
    monkeypatch.setattr(manager, 'start', lambda **kwargs: starts.append(kwargs))
    assert manager.auto_start() is use
    assert starts == ([{'download': True}] if use else [])
    manager.choose(not use)
    assert manager.chosen() is not use


def test_stop_api_still_terminates_the_model_when_preference_and_cleanup_fail(tmp_path, monkeypatch):
    from store_emulator.server import main
    from store_emulator.server.routes import system

    home = tmp_path / 'local'
    home.mkdir()
    (home / 'choice.json').write_text('{"use": true}')
    manager = LocalVLMManager(home)
    process = SimpleNamespace(returncode=None, poll=lambda: None)
    manager._proc = process
    manager._set(state='ready', managed=True, api_base='http://127.0.0.1:8081/v1')
    stopped = []
    monkeypatch.setattr(local_vlm, '_terminate', lambda proc: stopped.append(proc))
    monkeypatch.setattr(system, 'manager', lambda: manager)
    deny_choice_storage(monkeypatch, home, 'cleanup')
    response = TestClient(main.app, raise_server_exceptions=False).post('/api/system/local-model/stop')
    assert response.status_code == 200
    assert response.json()['state'] == 'off' and response.json()['managed'] is False
    assert stopped == [process] and manager.chosen() is False
    assert manager.auto_start() is False and manager._thread is None


def test_a_later_successful_save_persists_the_current_session_choice(tmp_path, monkeypatch):
    manager = LocalVLMManager(tmp_path)
    with monkeypatch.context() as broken:
        deny_choice_storage(broken, tmp_path, 'replace')
        manager.choose(False)
        assert manager.chosen() is False
    manager.choose(True)
    assert manager.chosen() is True and LocalVLMManager(tmp_path).chosen() is True
