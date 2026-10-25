"""Late interview responses and lock creation must not resurrect deleted runs."""

import pytest

from store_emulator.application import online, projects
from store_emulator.application.storage.setups import metadata_path
from tests.server.test_online_interview_api import PID, _run, _Shopper, client  # noqa: F401
from tests.server.test_shelf_lab_start_snapshot import overlap


@pytest.fixture
def conversation(client, monkeypatch):
    run_id, shopper = _run(client)
    monkeypatch.setattr(online, "assistive_client", lambda *_a, **_k: _Shopper())
    return client, run_id, shopper


@pytest.mark.parametrize("deleted", ["project", "run"])
@pytest.mark.parametrize("phase", ["model", "write", "delete_first"])
def test_interview_save_cannot_undo_deletion(conversation, monkeypatch, deleted, phase):
    client, run_id, shopper = conversation
    run_url = f"/api/projects/{PID}/online/runs/{run_id}"
    ask = lambda: client.post(f"{run_url}/sessions/0/{shopper}/interview",
                              json={"question": "Why did you leave?", "model": "openai/gpt-test"})
    delete = lambda: client.delete(f"/api/projects/{PID}" if deleted == "project" else run_url)
    if phase == "delete_first":
        removed, answered = overlap(monkeypatch, projects if deleted == "project" else online,
                                    "remove_tree", delete, ask)
    else:
        answered, removed = overlap(monkeypatch, online, "assistive_client" if phase == "model" else "write_json",
                                    ask, delete)
    assert removed.status_code == 200, removed.text
    assert answered.status_code == (200 if phase == "write" else 404), answered.text
    root = metadata_path(PID).parent
    assert not (root / "online" / "runs" / run_id).exists()
    assert root.exists() is (deleted == "run")


@pytest.mark.parametrize("deleted", ["project", "run"])
@pytest.mark.parametrize("operation", ["ask", "clear"])
def test_lock_acquisition_after_deletion_leaves_no_run_folder(conversation, monkeypatch, deleted, operation):
    client, run_id, shopper = conversation
    run_url = f"/api/projects/{PID}/online/runs/{run_id}"
    url = f"{run_url}/sessions/0/{shopper}/interview"
    original = online.FileLock
    triggered = False

    def deleting_lock(*args, **kwargs):
        nonlocal triggered
        if not triggered:
            triggered = True
            removed = client.delete(f"/api/projects/{PID}" if deleted == "project" else run_url)
            assert removed.status_code == 200, removed.text
        return original(*args, **kwargs)

    monkeypatch.setattr(online, "FileLock", deleting_lock)
    response = (client.delete(url) if operation == "clear" else
                client.post(url, json={"question": "Why?", "model": "openai/gpt-test"}))
    assert response.status_code == 404, response.text
    root = metadata_path(PID).parent
    assert not (root / "online" / "runs" / run_id).exists()
    assert root.exists() is (deleted == "run")


@pytest.mark.parametrize("second", ["ask", "clear"])
def test_an_inflight_answer_still_serializes_the_same_conversation(conversation, monkeypatch, second):
    client, run_id, shopper = conversation
    url = f"/api/projects/{PID}/online/runs/{run_id}/sessions/0/{shopper}/interview"
    ask = lambda: client.post(url, json={"question": "Why?", "model": "openai/gpt-test"})
    answered, blocked = overlap(monkeypatch, online, "assistive_client", ask,
                                 ask if second == "ask" else lambda: client.delete(url))
    assert answered.status_code == 200, answered.text
    assert blocked.status_code == 409, blocked.text
    assert len(client.get(url).json()["messages"]) == 2
