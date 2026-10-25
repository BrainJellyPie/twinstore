"""Talking to an online shopper through the API: the conversation is kept per store and shopper of a run."""

import time

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

PID = "proj_67916afd"


@pytest.fixture
def client(tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    with TestClient(app) as c:
        yield c


class _Shopper:
    async def generate_structured_async[T: BaseModel](self, response_model: type[T], system_prompt: str, user_prompt: str,
                                                      **_: object) -> T:
        return response_model.model_validate({"answer": "I couldn't find the size I wanted.", "steps": [1]})


class _Broken:
    async def generate_structured_async[T: BaseModel](self, response_model: type[T], *_: object, **__: object) -> T:
        raise RuntimeError("rate limited")


def _run(client: TestClient) -> tuple[str, str]:
    site = client.post(f"/api/projects/{PID}/online/sites", json={"template_id": "fashion"}).json()
    run = client.post(f"/api/projects/{PID}/online/runs", json={"site_ids": [site["id"]], "shoppers": 3}).json()
    for _ in range(300):
        view = client.get(f"/api/projects/{PID}/online/runs/{run['run_id']}").json()
        if view["status"]["status"] == "completed":
            return run["run_id"], view["result"]["shoppers"][0]["id"]
        time.sleep(0.1)
    raise AssertionError("run did not finish")


def test_a_conversation_with_one_shopper(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from store_emulator.application import online

    run_id, shopper = _run(client)
    url = f"/api/projects/{PID}/online/runs/{run_id}/sessions/0/{shopper}/interview"
    assert client.get(url).json()["messages"] == []
    assert client.get(f"/api/projects/{PID}/online/runs/{run_id}/sessions/0/nobody/interview").status_code == 404

    monkeypatch.setattr(online, "assistive_client", lambda *_a, **_k: _Shopper())
    talk = client.post(url, json={"question": "  Why did you leave?  ", "model": "openai/gpt-test"}).json()
    assert [(m["role"], m["text"]) for m in talk["messages"]] == [
        ("interviewer", "Why did you leave?"), ("shopper", "I couldn't find the size I wanted.")]
    assert talk["messages"][1]["steps"] == [1] and talk["model"] == "openai/gpt-test" and talk["variant"] == 0
    assert client.get(url).json() == talk
    assert client.post(url, json={"question": ""}).status_code == 422

    monkeypatch.setattr(online, "assistive_client", lambda *_a, **_k: _Broken())
    failed = client.post(url, json={"question": "And the price?", "model": "openai/gpt-test"})
    assert failed.status_code == 502 and "could not answer" in failed.json()["detail"]
    assert len(client.get(url).json()["messages"]) == 2  # a failed question is not kept

    assert client.delete(url).status_code == 200
    assert client.get(url).json()["messages"] == []
