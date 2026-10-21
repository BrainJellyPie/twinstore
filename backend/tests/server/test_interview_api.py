"""Shopper journeys and interviews on the sample run, with a fake language model (no network)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from store_emulator.application.storage.io import read_json, write_json

PID = "proj_67916afd"
RUN = "run_efd57c"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    with TestClient(app) as c:
        yield c


class _Fake:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def generate_structured_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str, *, max_retries: int = 1, seed: int | None = None,
    ) -> T:
        self.prompts.append(user_prompt)
        return response_model.model_validate({"answer": " I wanted something quick, so I grabbed the nuts. ", "steps": [2, 999]})


def _shopper(client) -> str:
    timeline = client.get(f"/api/projects/{PID}/runs/{RUN}/timeline").json()
    return next(c["persona_id"] for c in timeline if any(e["action"] == "buy" for e in c["timeline"]))


def test_journey_and_interview(client, monkeypatch):
    sid = _shopper(client)
    j = client.get(f"/api/projects/{PID}/runs/{RUN}/shoppers/{sid}/journey")
    assert j.status_code == 200, j.text
    journey = j.json()
    steps = journey["steps"]
    assert journey["persona"]["id"] == sid and journey["currency"] == "USD"
    assert [s["index"] for s in steps] == list(range(1, len(steps) + 1))
    assert steps[0]["action"] == "enter" and steps[0]["thought"] and steps[0]["time"] == journey["arrival_time"]
    assert all(s["action"] != "move" or s["thought"] or s["rack_id"] for s in steps)
    buys = [s for s in steps if s["action"] == "buy"]
    assert buys and sum(s["quantity"] for s in buys) == journey["units"]
    assert any(b["rack_id"] in journey["shelves"] for b in buys) and len(journey["path"]) >= len(steps)

    from store_emulator.application import interview
    fake = _Fake()
    monkeypatch.setattr(interview, "build_client", lambda *a, **k: fake)
    assert client.get(f"/api/projects/{PID}/runs/{RUN}/shoppers/{sid}/interview").json()["messages"] == []
    r = client.post(f"/api/projects/{PID}/runs/{RUN}/shoppers/{sid}/interview", json={"question": "Why did you buy that?"})
    assert r.status_code == 200, r.text
    msgs = r.json()["messages"]
    assert [m["role"] for m in msgs] == ["interviewer", "shopper"]
    assert msgs[1]["text"] == "I wanted something quick, so I grabbed the nuts." and msgs[1]["steps"] == [2]
    prompt = fake.prompts[0]
    assert "[1]" in prompt and steps[0]["thought"] in prompt and "Researcher: Why did you buy that?" in prompt
    client.post(f"/api/projects/{PID}/runs/{RUN}/shoppers/{sid}/interview", json={"question": "And the price?"})
    assert "Conversation so far:" in fake.prompts[1] and "You: I wanted something quick" in fake.prompts[1]
    assert len(client.get(f"/api/projects/{PID}/runs/{RUN}/shoppers/{sid}/interview").json()["messages"]) == 4
    assert client.delete(f"/api/projects/{PID}/runs/{RUN}/shoppers/{sid}/interview").status_code == 204
    assert client.get(f"/api/projects/{PID}/runs/{RUN}/shoppers/{sid}/interview").json()["messages"] == []


def test_unknown_shopper_and_bad_ids(client):
    assert client.get(f"/api/projects/{PID}/runs/{RUN}/shoppers/NOBODY/journey").status_code == 404
    assert client.get(f"/api/projects/{PID}/runs/{RUN}/shoppers/a.b/journey").status_code == 400
    assert client.get(f"/api/projects/{PID}/runs/run_missing/shoppers/M1/journey").status_code == 404


def test_town_shopper_can_view_journey_and_complete_interview(client, monkeypatch):
    source_id = _shopper(client)
    shopper_id = f"{source_id}~t1"
    output = Path(".data") / PID / "runs" / RUN / "output"
    customers = read_json(output / "timeline.json")
    customer = next(c for c in customers if c["persona_id"] == source_id)
    customer["persona_id"] = shopper_id
    write_json(output / "timeline.json", [customer])
    persona = read_json(output / "personas.json")[source_id]
    persona["id"] = shopper_id
    write_json(output / "personas.json", {shopper_id: persona})
    from store_emulator.application import interview
    monkeypatch.setattr(interview, "build_client", lambda *a, **k: _Fake())
    url = f"/api/projects/{PID}/runs/{RUN}/shoppers/{shopper_id}"

    journey = client.get(f"{url}/journey")
    assert journey.status_code == 200, journey.text
    assert journey.json()["persona"]["id"] == shopper_id
    reply = client.post(f"{url}/interview", json={"question": "Why did you visit?"})
    assert reply.status_code == 200, reply.text
    assert len(client.get(f"{url}/interview").json()["messages"]) == 2
    assert client.delete(f"{url}/interview").status_code == 204


def test_model_errors_are_reported(client, monkeypatch):
    sid = _shopper(client)

    class _Broken:
        async def generate_structured_async(self, *a: object, **k: object) -> BaseModel:
            raise TimeoutError("provider timed out")

    from store_emulator.application import interview
    monkeypatch.setattr(interview, "build_client", lambda *a, **k: _Broken())
    r = client.post(f"/api/projects/{PID}/runs/{RUN}/shoppers/{sid}/interview", json={"question": "Hello?"})
    assert r.status_code == 502 and "TimeoutError" in r.json()["detail"]
    assert client.get(f"/api/projects/{PID}/runs/{RUN}/shoppers/{sid}/interview").json()["messages"] == []
