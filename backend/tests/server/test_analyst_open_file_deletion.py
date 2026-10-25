"""Windows-style open-file deletion must not be blocked by a slow analyst's lock."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from store_emulator.application import projects, run_analyst
from store_emulator.application.storage.io import write_json
from store_emulator.application.storage.setups import metadata_path
from store_emulator.domain.interview import AnalystMessage, AnalystThread
from store_emulator.server.main import app
from tests.server.test_analyst_project_lifecycle import PID, RUN, URL, analyst
from tests.server.test_simulation_setup_races import layout


@pytest.mark.parametrize("existing", [False, True])
def test_project_deletion_can_finish_while_analyst_lock_is_open(analyst, monkeypatch, existing):
    _, base = analyst
    client = TestClient(app, raise_server_exceptions=False)
    if existing:
        write_json(base / "analyst.json", AnalystThread(run_id=RUN,
            messages=[AnalystMessage(role="user", text="Previous question")]).model_dump(mode="json"))
    active = []
    factory, remove = run_analyst.FileLock, projects.remove_tree

    def tracked_lock(*args, **kwargs):
        lock = factory(*args, **kwargs, thread_local=False)
        active.append(lock)
        return lock

    def windows_delete(path):
        # Windows refuses to unlink the open msvcrt lock handle; POSIX allows it.
        if any(lock.is_locked and Path(lock.lock_file).resolve().is_relative_to(Path(path).resolve()) for lock in active):
            raise PermissionError("[WinError 32] The file is being used by another process")
        return remove(path)

    seen = []
    class Model:
        async def generate_structured_async(self, schema, *args, **kwargs):
            assert any(lock.is_locked for lock in active)
            seen.append(client.delete(f"/api/projects/{PID}").status_code)
            return schema.model_validate({"answer": "One visitor bought tea."})

    monkeypatch.setattr(run_analyst, "FileLock", tracked_lock)
    monkeypatch.setattr(projects, "remove_tree", windows_delete)
    monkeypatch.setattr(run_analyst, "assistive_client", lambda *args, **kwargs: Model())
    result = client.post(URL, json={"question": "What happened?"})
    assert seen == [200]
    assert result.status_code == 404
    assert not metadata_path(PID).parent.exists() and not base.exists()
    assert all(not lock.is_locked for lock in active)
