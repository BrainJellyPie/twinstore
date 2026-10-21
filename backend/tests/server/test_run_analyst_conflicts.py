"""An accepted clear must not be undone by an already-running answer."""
import pytest
from fastapi.testclient import TestClient
from filelock import FileLock
from store_emulator.application import run_analyst
from store_emulator.application.storage.io import write_json
from store_emulator.domain.interview import AnalystThread, AnalystMessage

PID, RUN = 'proj_67916afd', 'run_efd57c'
URL = f'/api/projects/{PID}/runs/{RUN}/analyst'

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('TWINSTORE_LOCAL_VLM_AUTO', '0')
    from store_emulator.server.main import app
    with TestClient(app) as c:
        yield c

@pytest.mark.parametrize('existing', [False, True])
def test_clear_rejects_an_active_answer_then_can_be_retried(client, monkeypatch, existing):
    path = run_analyst._path(PID, RUN)
    if existing:
        write_json(path, AnalystThread(run_id=RUN, messages=[AnalystMessage(role='user', text='Previous question')]).model_dump())
    before = path.read_bytes() if path.exists() else None
    seen = {}
    class Fake:
        async def generate_structured_async(self, response_model, *args, **kwargs):
            seen['clear'] = client.delete(URL).status_code
            seen['preserved'] = (path.read_bytes() if path.exists() else None) == before
            return response_model.model_validate({'answer': 'One visitor bought tea.'})
    monkeypatch.setattr(run_analyst, 'build_client', lambda *a, **k: Fake())
    monkeypatch.setattr(run_analyst, 'facts', lambda *a: 'Visitors: 1.')
    response = client.post(URL, json={'question': 'What happened?'})
    assert response.status_code == 200, response.text
    assert seen == {'clear': 409, 'preserved': True}
    assert len(client.get(URL).json()['messages']) == (3 if existing else 2)
    assert client.delete(URL).status_code == 204
    assert client.get(URL).json()['messages'] == []

@pytest.mark.parametrize('method', ['post', 'delete'])
def test_answer_and_clear_share_the_same_lock(client, method):
    path = run_analyst._path(PID, RUN)
    with FileLock(path.with_suffix('.lock'), timeout=0):
        response = client.post(URL, json={'question': 'What happened?'}) if method == 'post' else client.delete(URL)
        assert response.status_code == 409
        assert client.get(URL).status_code == 200
    assert client.delete(URL).status_code == 204
