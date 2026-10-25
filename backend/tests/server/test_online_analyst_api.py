"""Questions about an online run: answered from the run's report, figures checked against it, kept with the run."""

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


class _Analyst:
    def __init__(self) -> None:
        self.prompts: list[tuple[str, str]] = []

    async def generate_structured_async[T: BaseModel](self, response_model: type[T], system_prompt: str, user_prompt: str,
                                                      **_: object) -> T:
        self.prompts.append((system_prompt, user_prompt))
        sheet = user_prompt.split("\n")
        used = next(line for line in sheet if "minus control" in line)
        return response_model.model_validate({"answer": "The variant converted about the same as the control.",
                                              "figures": [used, "conversion 99.9 % (made up)"],
                                              "follow_ups": ["Which shoppers changed their mind?",
                                                             "The variant converted about the same as the control.",
                                                             "which shoppers changed their mind"]})


class _Broken:
    async def generate_structured_async[T: BaseModel](self, response_model: type[T], *_: object, **__: object) -> T:
        raise RuntimeError("rate limited")


def _run(client: TestClient) -> str:
    site = client.post(f"/api/projects/{PID}/online/sites", json={"template_id": "fashion"}).json()
    options = {**site["options"], "page_style": "minimal", "quick_add": True}
    variant = client.post(f"/api/projects/{PID}/online/sites/{site['id']}/copy",
                          json={"name": "Quick add", "options": options}).json()
    run = client.post(f"/api/projects/{PID}/online/runs",
                      json={"site_ids": [site["id"], variant["id"]], "shoppers": 4}).json()
    for _ in range(300):
        view = client.get(f"/api/projects/{PID}/online/runs/{run['run_id']}").json()
        if view["status"]["status"] == "completed":
            return run["run_id"]
        time.sleep(0.1)
    raise AssertionError("run did not finish")


def test_questions_about_an_online_run(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from store_emulator.application import online

    run_id = _run(client)
    url = f"/api/projects/{PID}/online/runs/{run_id}/analyst"
    assert client.get(url).json() == {"run_id": run_id, "model": "", "messages": []}
    assert client.get(f"/api/projects/{PID}/online/runs/nope/analyst").status_code == 404

    facts = client.get(f"{url}/facts").text
    assert "Quick add minus control (same shoppers, 95 % interval)" in facts
    assert "funnel:" in facts and "visits ended:" in facts

    analyst = _Analyst()
    monkeypatch.setattr(online, "assistive_client", lambda *_a, **_k: analyst)
    thread = client.post(url, json={"question": " Did quick add help? ", "model": "openai/gpt-test"}).json()
    assert [(m["role"], m["text"]) for m in thread["messages"]] == [
        ("user", "Did quick add help?"), ("analyst", "The variant converted about the same as the control.")]
    answer = thread["messages"][1]
    assert len(answer["figures"]) == 1 and "minus control" in answer["figures"][0]  # the made-up figure is dropped
    # A follow-up that repeats the answer or another follow-up is dropped (small models do this).
    assert answer["follow_ups"] == ["Which shoppers changed their mind?"] and thread["model"] == "openai/gpt-test"
    system, user = analyst.prompts[0]
    assert "online" in system and "Write in English." in system and "Manager: Did quick add help?" in user
    assert client.get(url).json() == thread

    client.post(url, json={"question": "And on phones?", "model": "openai/gpt-test"})
    assert "Manager: Did quick add help?" in analyst.prompts[1][1]  # the conversation so far goes along

    monkeypatch.setattr(online, "assistive_client", lambda *_a, **_k: _Broken())
    failed = client.post(url, json={"question": "And the price?", "model": "openai/gpt-test"})
    assert failed.status_code == 502 and "could not be answered" in failed.json()["detail"]
    assert len(client.get(url).json()["messages"]) == 4  # a failed question is not kept

    assert client.delete(url).status_code == 200
    assert client.get(url).json()["messages"] == []


class _Starters:
    async def generate_structured_async[T: BaseModel](self, response_model: type[T], system_prompt: str, user_prompt: str,
                                                      **_: object) -> T:
        assert "online run" in system_prompt and "Fact sheet:" in user_prompt
        return response_model.model_validate({"questions": ["Why do phone shoppers leave at the cart?",
                                                            "why do phone shoppers leave at the cart?", "Short?"]})


def test_starter_questions_are_read_off_the_run(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from store_emulator.application import online

    run_id = _run(client)
    monkeypatch.setattr(online, "assistive_client", lambda *_a, **_k: _Starters())
    r = client.post(f"/api/projects/{PID}/online/runs/{run_id}/analyst/suggestions", json={"model": "openai/gpt-test"})
    assert r.status_code == 200, r.text
    assert r.json() == ["Why do phone shoppers leave at the cart?"]  # repeats and fragments are dropped
    assert client.get(f"/api/projects/{PID}/online/runs/{run_id}/analyst").json()["messages"] == []  # nothing is kept
