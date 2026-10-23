"""Slow analyst replies and lock files must not resurrect a deleted project."""

import pytest
from fastapi.testclient import TestClient
from filelock import FileLock

from store_emulator.application import projects, run_analyst, setups
from store_emulator.application.storage.io import write_json
from store_emulator.application.storage.setups import metadata_path
from store_emulator.domain.interview import AnalystMessage, AnalystThread
from store_emulator.server.main import app
from tests.server.test_shelf_lab_start_snapshot import overlap
from tests.server.test_simulation_setup_races import PID, layout

RUN = "run_analyst_lifecycle"
URL = f"/api/projects/{PID}/runs/{RUN}/analyst"


@pytest.fixture
def analyst(layout, monkeypatch):
    base = metadata_path(PID).parent / "runs" / RUN
    write_json(base / "output" / "timeline.json", [])
    monkeypatch.setattr(run_analyst, "facts", lambda *args: "Visitors: 1.")

    class Fake:
        async def generate_structured_async(self, response_model, *args, **kwargs):
            return response_model.model_validate({"answer": "One visitor."})

    monkeypatch.setattr(run_analyst, "assistive_client", lambda *args, **kwargs: Fake())
    return TestClient(app), base


@pytest.mark.parametrize("existing", [False, True])
@pytest.mark.parametrize("phase", ["answer", "write", "delete_first", "lock"])
def test_answer_and_project_deletion_cannot_leave_orphaned_files(analyst, monkeypatch, existing, phase):
    client, base = analyst
    path = base / "analyst.json"
    if existing:
        write_json(path, AnalystThread(run_id=RUN, messages=[AnalystMessage(role="user", text="Before")]).model_dump())
    ask = lambda: client.post(URL, json={"question": "What happened?"})
    delete = lambda: client.delete(f"/api/projects/{PID}")
    if phase == "delete_first":
        removed, answered = overlap(monkeypatch, projects, "remove_tree", delete, ask)
    elif phase == "lock":
        # Pause before the transcript lock can create its file; let deletion finish.
        original = run_analyst.FileLock

        def deleting_lock(*args, **kwargs):
            response = delete()
            assert response.status_code == 200, response.text
            return original(*args, **kwargs)

        monkeypatch.setattr(run_analyst, "FileLock", deleting_lock)
        answered = ask()
        removed = None
    else:
        method = "answered_by" if phase == "answer" else "write_json"
        answered, removed = overlap(monkeypatch, run_analyst, method, ask, delete)
    if removed is not None:
        assert removed.status_code == 200, removed.text
    assert answered.status_code == (200 if phase == "write" else 404), answered.text
    assert not metadata_path(PID).parent.exists()
    assert not base.exists()


@pytest.mark.parametrize("operation", ["ask", "clear"])
def test_busy_project_preserves_the_previous_thread(analyst, monkeypatch, operation):
    client, base = analyst
    assert client.post(URL, json={"question": "What happened?"}).status_code == 200
    before = (base / "analyst.json").read_bytes()
    monkeypatch.setattr(setups, "FileLock", lambda path, timeout: FileLock(path, timeout=0))
    with FileLock(setups.setup_lock_path(PID, "tree").with_name(".setup-tree.lock"), timeout=0):
        response = client.post(URL, json={"question": "Next?"}) if operation == "ask" else client.delete(URL)
    assert response.status_code == 503, response.text
    assert (base / "analyst.json").read_bytes() == before
