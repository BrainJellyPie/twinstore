"""A damaged or unwritable record must not prevent unrelated projects from restarting."""
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from store_emulator.application import marketing
from store_emulator.application.storage import generations, setups
from store_emulator.application.storage.io import read_json, write_json
from store_emulator.domain.marketing import JobStatus

KINDS = ['setup', 'generation', 'marketing']


def record(kind, project, name, state='running'):
    root = Path('.data') / project
    if kind == 'setup':
        return root / 'setups' / f'{name}.json', {'id': name, 'status': state, 'store': {'name': 'Preserve me'}}
    if kind == 'generation':
        return root / 'generations' / name / 'status.json', {'status': state, 'kind': 'persona', 'setup_id': 'setup_good', 'progress': {'count': 3}}
    return root / 'marketing' / 'experiments' / name / 'status.json', JobStatus(job_id=name, kind='experiment', name='Preserve me', status=state).model_dump(mode='json')


def recovery(kind):
    return {'setup': setups.recover_running_setups, 'generation': generations.recover_running_generations, 'marketing': marketing.recover_running_jobs}[kind]


@pytest.fixture
def startup(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('TWINSTORE_LOCAL_VLM_AUTO', '0')
    from store_emulator.server import main
    monkeypatch.setattr(main, 'seed_sample_projects', lambda: 0)
    manager = Mock()
    monkeypatch.setattr(main, 'local_vlm', lambda: manager)
    yield main.app
    manager.start.assert_not_called()


def healthy_records(kind):
    healthy, data = record(kind, 'proj_good', 'good')
    write_json(healthy, data)
    finished, data = record(kind, 'proj_good', 'finished', 'completed')
    write_json(finished, data)
    return healthy, finished, finished.read_bytes()


def assert_healthy(kind, healthy, finished, saved):
    current = read_json(healthy)
    assert current['status'] == ('draft' if kind == 'setup' else 'failed')
    if kind != 'setup':
        assert 'restart' in current['error']
    if kind == 'generation':
        assert current['progress'] == {'count': 3}
    if kind == 'setup':
        assert current['store'] == {'name': 'Preserve me'}
    assert finished.read_bytes() == saved
    assert recovery(kind)() == 0


@pytest.mark.parametrize('kind', KINDS)
@pytest.mark.parametrize('raw', [b'', b'{"status":', b'null', b'[]', b'"running"', b'42', b'false', b'\xff'])
def test_restart_preserves_corrupt_record_and_recovers_other_projects(startup, caplog, kind, raw):
    bad, _ = record(kind, 'proj_bad', 'bad')
    bad.parent.mkdir(parents=True)
    bad.write_bytes(raw)
    healthy, finished, saved = healthy_records(kind)
    with TestClient(startup) as client:
        assert client.get('/api/health').status_code == 200
    assert bad.read_bytes() == raw
    assert str(bad) in caplog.text
    assert_healthy(kind, healthy, finished, saved)


@pytest.mark.parametrize('kind', KINDS)
@pytest.mark.parametrize('operation', ['read', 'write'])
def test_restart_isolates_record_io_failure(startup, monkeypatch, caplog, kind, operation):
    bad, data = record(kind, 'proj_bad', 'bad')
    write_json(bad, data)
    original = bad.read_bytes()
    healthy, finished, saved = healthy_records(kind)
    module = {'setup': setups, 'generation': generations, 'marketing': marketing}[kind]
    name = f'{operation}_json'
    original_function = getattr(module, name)
    def fail_one(path, *args):
        if path == bad:
            raise PermissionError('record unavailable for this test')
        return original_function(path, *args)
    monkeypatch.setattr(module, name, fail_one)
    with TestClient(startup) as client:
        assert client.get('/api/health').status_code == 200
    assert bad.read_bytes() == original
    assert str(bad) in caplog.text
    assert_healthy(kind, healthy, finished, saved)


@pytest.mark.parametrize('kind', KINDS)
@pytest.mark.parametrize('state', ['pending', 'running', 'completed', 'failed'])
def test_restart_only_changes_interrupted_records(startup, kind, state):
    path, data = record(kind, 'proj_test', 'tracked', state)
    write_json(path, data)
    original = path.read_bytes()
    interrupted = state == 'running' or (state == 'pending' and kind != 'setup')
    assert recovery(kind)() == int(interrupted)
    if interrupted:
        updated = read_json(path)
        assert updated['status'] == ('draft' if kind == 'setup' else 'failed')
    else:
        assert path.read_bytes() == original
    assert recovery(kind)() == 0
