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
    seen = next(s for s in steps if s["action"] in ("browse", "buy") and s["face"] and s["sees_products"])
    png = client.get(f"/api/projects/{PID}/runs/{RUN}/racks/{seen['rack_id']}/faces/{seen['face']}.png")
    assert png.status_code == 200 and png.content[:4] == b"\x89PNG"
    assert client.get(f"/api/projects/{PID}/runs/{RUN}/racks/{seen['rack_id']}/faces/Q.png").status_code == 400

    from store_emulator.application import interview
    fake = _Fake()
    monkeypatch.setattr(interview, "assistive_client", lambda *a, **k: fake)
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
    monkeypatch.setattr(interview, "assistive_client", lambda *a, **k: _Fake())
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
    monkeypatch.setattr(interview, "assistive_client", lambda *a, **k: _Broken())
    r = client.post(f"/api/projects/{PID}/runs/{RUN}/shoppers/{sid}/interview", json={"question": "Hello?"})
    assert r.status_code == 502 and r.json()["detail"] == "The shopper could not answer: the model took too long to reply. Try again."
    assert client.get(f"/api/projects/{PID}/runs/{RUN}/shoppers/{sid}/interview").json()["messages"] == []


class _Group:
    def __init__(self) -> None:
        self.calls = 0

    async def generate_structured_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str, *, max_retries: int = 1, seed: int | None = None,
    ) -> T:
        self.calls += 1
        if "themes" in response_model.model_fields:
            n = user_prompt.count("\n") - 2
            return response_model.model_validate({"themes": ["Nothing I needed", "Too expensive"], "assignments": [i % 2 for i in range(n - 1)] + [7]})
        return response_model.model_validate({"answer": "Nothing caught my eye.", "steps": [1]})


def test_group_interview_codes_themes(client, monkeypatch):
    from store_emulator.application import interview
    fake = _Group()
    monkeypatch.setattr(interview, "assistive_client", lambda *a, **k: fake)
    empty = client.post(f"/api/projects/{PID}/runs/{RUN}/group-interviews",
                        json={"question": "Why did you leave without buying?", "segment": "empty_handed", "size": 6}).json()
    assert empty["answers"] and all(a["units"] == 0 for a in empty["answers"])
    r = client.post(f"/api/projects/{PID}/runs/{RUN}/group-interviews", json={"question": "What did you think of the store?", "size": 6})
    assert r.status_code == 200, r.text
    g = r.json()
    assert len(g["answers"]) == 6 and g["errors"] == 0
    labels = [t["label"] for t in g["themes"]]
    assert labels[:2] == ["Nothing I needed", "Too expensive"] and labels[-1] == "Other"   # the misnumbered answer
    assert sum(t["count"] for t in g["themes"]) == 6 and all(0 <= a["theme"] < len(labels) for a in g["answers"])
    assert {x["group_id"] for x in client.get(f"/api/projects/{PID}/runs/{RUN}/group-interviews").json()} == {g["group_id"], empty["group_id"]}
    picked = client.post(f"/api/projects/{PID}/runs/{RUN}/group-interviews", json={"question": "Hi?", "persona_ids": ["NOBODY"]})
    assert picked.status_code == 404
    assert client.delete(f"/api/projects/{PID}/runs/{RUN}/group-interviews/{g['group_id']}").status_code == 204


class _Ideas:
    def __init__(self, questions: list[str]) -> None:
        self.questions = questions
        self.calls: list[str] = []

    async def generate_structured_async[T: BaseModel](
        self, response_model: type[T], system_prompt: str, user_prompt: str, *, max_retries: int = 1, seed: int | None = None,
    ) -> T:
        self.calls.append(user_prompt)
        if response_model.__name__ == "FollowUps":
            return response_model.model_validate({"questions": self.questions})
        return response_model.model_validate({"answer": "The nuts were on offer.", "steps": [2]})


def test_follow_up_questions_are_written_for_the_trip_and_kept_until_the_conversation_moves(client, monkeypatch):
    from store_emulator.application import interview
    sid = _shopper(client)
    url = f"/api/projects/{PID}/runs/{RUN}/shoppers/{sid}/interview"
    fake = _Ideas(["What drew you to the nuts", "What drew you to the nuts?", "  ", "Did the price tag matter?",
                   "Would you buy them again?", "One more?"])
    monkeypatch.setattr(interview, "assistive_client", lambda *a, **k: fake)
    r = client.post(f"{url}/suggestions", json={})
    assert r.status_code == 200, r.text
    body = r.json()
    # Duplicates and blanks dropped, a question mark added, three at most; written in the observer's voice.
    assert body["suggestions"] == ["What drew you to the nuts?", "Did the price tag matter?", "Would you buy them again?"]
    assert body["suggested_after"] == 0 and body["messages"] == []
    assert "The shopper:" in fake.calls[0] and "Their trip" in fake.calls[0] and "No questions asked yet." in fake.calls[0]
    # Stored: asking again for the same conversation costs no model call.
    assert client.post(f"{url}/suggestions", json={}).json()["suggestions"] == body["suggestions"] and len(fake.calls) == 1
    assert client.get(url).json()["suggested_after"] == 0
    # A new turn makes them stale; the next suggestions see the conversation and skip what was already asked.
    fake.questions = ["Did the price tag matter?", "Was the offer the reason?"]
    turn = client.post(url, json={"question": "Did the price tag matter?"}).json()
    assert len(turn["messages"]) == 2 and turn["suggested_after"] == 0
    after = client.post(f"{url}/suggestions", json={}).json()
    assert after["suggestions"] == ["Was the offer the reason?"] and after["suggested_after"] == 2
    assert "Researcher: Did the price tag matter?" in fake.calls[-1] and "Shopper: The nuts were on offer." in fake.calls[-1]


def test_follow_up_failure_is_a_502_and_saves_nothing(client, monkeypatch):
    from store_emulator.application import interview

    class _Broken:
        async def generate_structured_async(self, *a, **k):
            raise RuntimeError("provider down")

    sid = _shopper(client)
    monkeypatch.setattr(interview, "assistive_client", lambda *a, **k: _Broken())
    url = f"/api/projects/{PID}/runs/{RUN}/shoppers/{sid}/interview"
    r = client.post(f"{url}/suggestions", json={})
    assert r.status_code == 502 and "provider down" in r.text
    assert client.get(url).json()["suggested_after"] == -1


def test_group_questions_are_read_off_the_run(client, monkeypatch):
    from store_emulator.application import interview

    class _Planner:
        def __init__(self) -> None:
            self.prompt = ""

        async def generate_structured_async[T: BaseModel](
            self, response_model: type[T], system_prompt: str, user_prompt: str, *, max_retries: int = 1, seed: int | None = None,
        ) -> T:
            self.prompt = user_prompt
            return response_model.model_validate({"questions": [
                {"question": "Why did you stop at the snacks but not buy", "segment": "empty_handed", "why": "many stops, few buys"},
                {"question": "Why did you stop at the snacks but not buy?", "segment": "all"},
                {"question": "What made you grab the jerky?", "segment": "impulse", "why": "top impulse pick"},
                {"question": "Walk me through your last stop.", "segment": "buyers"},
            ]})

    fake = _Planner()
    monkeypatch.setattr(interview, "assistive_client", lambda *a, **k: fake)
    r = client.post(f"/api/projects/{PID}/runs/{RUN}/group-interviews/suggestions", json={})
    assert r.status_code == 200, r.text
    ideas = r.json()
    assert [(i["question"], i["segment"]) for i in ideas] == [
        ("Why did you stop at the snacks but not buy?", "empty_handed"), ("What made you grab the jerky?", "impulse"),
        ("Walk me through your last stop.", "buyers")]
    assert fake.prompt.startswith("Shoppers: ") and "Shelves where shoppers stopped (stopped / bought there):" in fake.prompt
