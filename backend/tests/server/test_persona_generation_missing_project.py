"""Missing projects must be rejected before persona jobs are queued."""
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from store_emulator.application import generation_async
from store_emulator.application.storage.io import write_json
from store_emulator.application.storage.setups import new_setup_data


@pytest.mark.parametrize("metadata_exists", [False, True])
def test_persona_job_requires_real_project(tmp_path, monkeypatch, metadata_exists):
    monkeypatch.chdir(tmp_path)
    root = tmp_path / ".data" / "proj_test"
    setup = new_setup_data("Source", None, None)
    setup["id"] = "setup_test"
    write_json(root / "setups" / "setup_test.json", setup)
    if metadata_exists:
        write_json(root / "metadata.json", {"name": "Test", "currency": "USD"})
    before = set(tmp_path.rglob("*"))
    executor = Mock()
    monkeypatch.setattr(generation_async, "executor", executor)
    from store_emulator.server.main import app
    response = TestClient(app, raise_server_exceptions=False).post("/api/projects/proj_test/setups/setup_test/regenerate-persona")
    assert response.status_code == (200 if metadata_exists else 404), response.text
    if metadata_exists:
        executor.submit.assert_called_once()
    else:
        executor.submit.assert_not_called()
        assert set(tmp_path.rglob("*")) == before
