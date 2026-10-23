"""Stored customer labels remain usable without becoming filesystem paths."""

import json
from pathlib import Path
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from store_emulator.application import interview
from store_emulator.application.storage.io import write_json
from store_emulator.domain.config import SimulationConfig
from store_emulator.domain.interview import Interview, InterviewMessage, InterviewQuestion
from tests.server.test_interview_api import _Fake


@pytest.fixture
def saved_run(tmp_path, monkeypatch):
    sample = Path(__file__).resolve().parents[2] / "sample_data/proj_67916afd/runs/run_efd57c"
    customer = json.loads((sample / "output/timeline.json").read_text())[0]
    persona = json.loads((sample / "output/personas.json").read_text())[customer["persona_id"]]
    store = json.loads((sample / "input/store.json").read_text())
    monkeypatch.chdir(tmp_path)
    base = tmp_path / ".data/project/runs/run"
    write_json(base.parent.parent / "metadata.json", {"name": "Customer identifier test"})
    write_json(base / "input/store.json", store)
    monkeypatch.setattr(interview, "assistive_client", lambda *a, **kw: _Fake())

    def save(ids):
        write_json(base / "output/timeline.json", [{**customer, "persona_id": sid} for sid in ids])
        write_json(base / "output/personas.json", {sid: {**persona, "id": sid} for sid in ids})
        interview._run_data.cache_clear()
        return base

    yield save
    interview._run_data.cache_clear()


@pytest.mark.parametrize("sid", [
    "고객-001", "顧客001", "cliente-é", "cliente-e\u0301", "customer 😀", "customer A", " customer ",
    "x" * 80, "x" * 81, "x" * 512, "x" * 80 + "~s1", "x" * 80 + "~t1-08h-linked-cafe-30s-0",
    "a.b", "a?b#c", "@customer", "001", "NULL",
])
def test_saved_ids_can_read_journey_and_complete_interview(saved_run, sid):
    base = saved_run([sid])
    from store_emulator.server.main import app
    client = TestClient(app)
    url = f"/api/projects/project/runs/run/shoppers/{quote(sid, safe='')}"
    journey = client.get(f"{url}/journey")
    assert journey.status_code == 200, journey.text
    assert journey.json()["persona"]["id"] == sid
    assert client.get(f"{url}/interview").json()["messages"] == []
    reply = client.post(f"{url}/interview", json={"question": "Why did you visit?"})
    assert reply.status_code == 200, reply.text
    assert reply.json()["persona_id"] == sid and len(reply.json()["messages"]) == 2
    paths = list((base / "interviews").rglob("*.json"))
    assert len(paths) == 1 and len(paths[0].name) <= 85
    assert client.get(f"{url}/interview").json()["messages"] == reply.json()["messages"]
    assert client.delete(f"{url}/interview").status_code == 204
    assert client.get(f"{url}/interview").json()["messages"] == []


@pytest.mark.parametrize("sid", ["../outside", "../../metadata", "a/b", "a\\b"])
def test_arbitrary_stored_ids_never_become_relative_paths(saved_run, sid):
    base = saved_run([sid])
    result = interview.interview("project", "run", sid, InterviewQuestion(question="Why?"), SimulationConfig())
    assert result.persona_id == sid
    assert interview.get_journey("project", "run", sid).persona.id == sid
    paths = list(base.rglob("*.json"))
    transcripts = [p for p in paths if "interviews" in p.parts]
    assert len(transcripts) == 1
    assert transcripts[0].is_relative_to(base / "interviews")
    assert not (base / "outside.json").exists()
    assert not (base.parent / "metadata.json").exists()


def test_existing_safe_id_transcripts_remain_readable_and_new_ids_stay_distinct(saved_run):
    from hashlib import sha256
    unicode_id = "고객-001"
    digest = sha256(unicode_id.encode()).hexdigest()
    ids = ["M1", unicode_id, digest, "cliente-é", "cliente-e\u0301"]
    base = saved_run(ids)
    legacy = Interview(run_id="run", persona_id="M1", messages=[InterviewMessage(role="shopper", text="Existing answer")])
    write_json(base / "interviews/M1.json", legacy.model_dump(mode="json"))
    assert interview.get_interview("project", "run", "M1") == legacy
    for sid in ids[1:]:
        interview.interview("project", "run", sid, InterviewQuestion(question=f"For {sid}?"), SimulationConfig())
    assert len(list((base / "interviews").rglob("*.json"))) == len(ids)
    for sid in ids[1:]:
        answer = interview.get_interview("project", "run", sid)
        assert answer.persona_id == sid and answer.messages[0].text == f"For {sid}?"
    interview.clear_interview("project", "run", unicode_id)
    assert not interview.get_interview("project", "run", unicode_id).messages
    assert len(interview.get_interview("project", "run", digest).messages) == 2
    assert interview.get_interview("project", "run", "M1") == legacy
