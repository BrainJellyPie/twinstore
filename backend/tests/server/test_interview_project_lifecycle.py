"""Interview, follow-up and group saves cannot undo project deletion."""

import pytest
from fastapi.testclient import TestClient

from store_emulator.application import interview, projects
from store_emulator.application.storage.io import read_json, write_json
from store_emulator.application.storage.setups import metadata_path, personas_path, read_setup
from store_emulator.domain.customer import CustomerResult, TimelineEvent
from store_emulator.domain.types import Action, Weekday
from store_emulator.server.main import app
from tests.server.test_shelf_lab_start_snapshot import overlap
from tests.server.test_simulation_setup_races import PID, SID, layout

RUN = "run_interview_lifecycle"


@pytest.fixture(params=["p", "customer/한글~t2"], ids=["legacy", "path-id"])
def conversation(layout, monkeypatch, request):
    shopper = request.param
    base = metadata_path(PID).parent / "runs" / RUN
    person = {**read_json(personas_path(PID))[0], "id": shopper}
    customer = CustomerResult(persona_id=shopper, day=Weekday.MON, arrival_time="10:00:00", timeline=[
        TimelineEvent(elapsed_sec=0, x=0, y=0, action=Action.ENTER),
        TimelineEvent(elapsed_sec=10, x=0, y=0, action=Action.EXIT),
    ])
    write_json(base / "input" / "store.json", read_setup(PID, SID)["store"])
    write_json(base / "output" / "timeline.json", [customer.model_dump(mode="json")])
    write_json(base / "output" / "personas.json", {shopper: person})

    class Fake:
        async def generate_structured_async(self, response_model, *args, **kwargs):
            return response_model.model_validate({"answer": "I was browsing.", "steps": [],
                                                  "questions": ["What did you notice?"]})

    monkeypatch.setattr(interview, "assistive_client", lambda *args, **kwargs: Fake())
    return TestClient(app), shopper, base


def send(client, shopper, kind):
    url = f"/api/projects/{PID}/runs/{RUN}"
    if kind == "group":
        return client.post(f"{url}/group-interviews", json={"question": "Why?", "persona_ids": [shopper]})
    url += f"/shoppers/{shopper}/interview"
    if kind == "clear":
        return client.delete(url)
    return client.post(url + ("/suggestions" if kind == "suggestions" else ""),
                       json={} if kind == "suggestions" else {"question": "Why?"})


@pytest.mark.parametrize("kind", ["ask", "suggestions", "group"])
@pytest.mark.parametrize("phase", ["model", "write", "delete_first"])
def test_deletion_and_interview_writes_leave_no_project(conversation, monkeypatch, kind, phase):
    client, shopper, base = conversation
    save = lambda: send(client, shopper, kind)
    delete = lambda: client.delete(f"/api/projects/{PID}")
    if phase == "delete_first":
        removed, saved = overlap(monkeypatch, projects, "remove_tree", delete, save)
    else:
        method = "assistive_client" if phase == "model" else "write_json"
        saved, removed = overlap(monkeypatch, interview, method, save, delete)
    assert removed.status_code == 200, removed.text
    assert saved.status_code == (200 if phase == "write" else 404), saved.text
    assert not metadata_path(PID).parent.exists()
    assert not base.exists()


@pytest.mark.parametrize("kind", ["ask", "clear", "suggestions"])
def test_lock_acquisition_after_deletion_cannot_recreate_project(conversation, monkeypatch, kind):
    client, shopper, base = conversation
    original = interview.FileLock

    def deleting_lock(*args, **kwargs):
        deleted = client.delete(f"/api/projects/{PID}")
        assert deleted.status_code == 200, deleted.text
        return original(*args, **kwargs)

    monkeypatch.setattr(interview, "FileLock", deleting_lock)
    response = send(client, shopper, kind)
    assert response.status_code == 404, response.text
    assert not metadata_path(PID).parent.exists()
    assert not base.exists()


@pytest.mark.parametrize("pid,rid,status", [("bad!", RUN, 400), (PID, "bad!", 400),
                                            ("missing", RUN, 404), (PID, "missing", 404)])
@pytest.mark.parametrize("kind", ["group", "suggestions"])
def test_invalid_or_missing_resources_keep_their_client_errors(conversation, pid, rid, status, kind):
    client, shopper, _ = conversation
    url = f"/api/projects/{pid}/runs/{rid}"
    suffix = "/group-interviews" if kind == "group" else f"/shoppers/{shopper}/interview/suggestions"
    response = client.post(url + suffix, json={"question": "Why?"} if kind == "group" else {})
    assert response.status_code == status, response.text
