"""A missing image lookup must not create per-project storage."""

import pytest
from fastapi.testclient import TestClient

from store_emulator.application.storage.io import write_json


@pytest.mark.parametrize("project_exists", [False, True])
def test_missing_image_lookup_does_not_create_storage(tmp_path, monkeypatch, project_exists):
    monkeypatch.chdir(tmp_path)
    if project_exists:
        write_json(tmp_path / ".data" / "proj_test" / "metadata.json", {"currency": "USD"})
    before = {p.relative_to(tmp_path) for p in tmp_path.rglob("*")}

    from store_emulator.server.main import app

    response = TestClient(app).get("/api/projects/proj_test/images/not_uploaded")

    assert response.status_code == 404, response.text
    assert {p.relative_to(tmp_path) for p in tmp_path.rglob("*")} == before
