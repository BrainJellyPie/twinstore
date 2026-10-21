"""Empty interview input and model replies must not become persisted conversations."""

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from store_emulator.application.errors import AppError

PID = "proj_67916afd"
RUN = "run_efd57c"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize("endpoint,service_name", [("shoppers/M1/interview", "interview"), ("group-interviews", "group_interview")])
@pytest.mark.parametrize("question", [" ", "\t\n", "\u3000"])
def test_blank_question_rejected_before_service(client, monkeypatch, endpoint, service_name, question):
    from store_emulator.application import interview
    calls = []

    def called(*args):
        calls.append(args)
        raise AppError("Unexpected interview dispatch", 409)

    monkeypatch.setattr(interview, service_name, called)
    response = client.post(f"/api/projects/{PID}/runs/{RUN}/{endpoint}", json={"question": question})

    assert response.status_code == 422, response.text
    assert calls == []


@pytest.mark.parametrize("answer", ["", " \t\n"])
def test_blank_model_answer_is_reported_without_saving(client, monkeypatch, answer):
    from store_emulator.application import interview

    class BlankModel:
        async def generate_structured_async[T: BaseModel](self, response_model: type[T], *args, **kwargs) -> T:
            return response_model.model_validate({"answer": answer, "steps": []})

    monkeypatch.setattr(interview, "build_client", lambda *args, **kwargs: BlankModel())
    shopper = client.get(f"/api/projects/{PID}/runs/{RUN}/timeline").json()[0]["persona_id"]
    url = f"/api/projects/{PID}/runs/{RUN}/shoppers/{shopper}/interview"
    response = client.post(url, json={"question": "Why did you visit?"})

    assert response.status_code == 502, response.text
    assert client.get(url).json()["messages"] == []
