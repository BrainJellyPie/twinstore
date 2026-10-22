"""A delayed follow-up must belong to the conversation currently stored."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

PID = 'proj_67916afd'
RUN = 'run_efd57c'

@pytest.mark.parametrize('change', ['clear', 'append', 'restart', 'restart_with_fresh_suggestions'])
@pytest.mark.parametrize('same_question', [False, True])
def test_delayed_follow_ups_do_not_cross_a_conversation_restart(tmp_path, monkeypatch, change, same_question):
    monkeypatch.chdir(tmp_path)
    from store_emulator.application import interview
    from store_emulator.server.main import app
    entered, release = Event(), Event()
    calls = []

    class Model:
        async def generate_structured_async[T: BaseModel](self, response_model: type[T], system_prompt, user_prompt, **kwargs) -> T:
            if response_model.__name__ != 'FollowUps':
                return response_model.model_validate({'answer': 'The answer to this question.', 'steps': []})
            calls.append(user_prompt)
            if len(calls) == 1:
                entered.set()
                assert release.wait(10), 'Test did not release fake follow-up generation'
                questions = ['Old conversation follow-up?']
            else:
                questions = ['New conversation follow-up?']
            return response_model.model_validate({'questions': questions})

    monkeypatch.setattr(interview, 'assistive_client', lambda *args, **kwargs: Model())
    with TestClient(app) as client, ThreadPoolExecutor(max_workers=1) as pool:
        sid = client.get(f'/api/projects/{PID}/runs/{RUN}/timeline').json()[0]['persona_id']
        url = f'/api/projects/{PID}/runs/{RUN}/shoppers/{sid}/interview'
        assert client.post(url, json={'question': 'Original question?'}).status_code == 200
        pending = pool.submit(client.post, f'{url}/suggestions', json={})
        try:
            assert entered.wait(5)
            if change != 'append':
                assert client.delete(url).status_code == 204
            if change != 'clear':
                question = 'Original question?' if same_question else 'Different question?'
                assert client.post(url, json={'question': question}).status_code == 200
            if change == 'restart_with_fresh_suggestions':
                fresh = client.post(f'{url}/suggestions', json={})
                assert fresh.status_code == 200
                assert fresh.json()['suggestions'] == ['New conversation follow-up?']
            before = client.get(url).json()
        finally:
            release.set()
        response = pending.result(timeout=5)
        assert response.status_code == 200, response.text
        after = client.get(url).json()
        assert after == before
        assert response.json() == before
        assert 'Old conversation follow-up?' not in after['suggestions']
