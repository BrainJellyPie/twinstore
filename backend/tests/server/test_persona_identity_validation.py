"""Persona identity errors must not overwrite a project's usable customer pool."""

import json

import pytest
from fastapi.testclient import TestClient

from store_emulator.domain.persona import Persona
from store_emulator.server.main import app


@pytest.mark.parametrize("duplicate_id", ["p_test", "", "   "])
def test_persona_ids_are_unique_and_nonempty_before_save(tmp_path, monkeypatch, duplicate_id):
    monkeypatch.chdir(tmp_path)
    root = tmp_path / ".data" / "proj_test"
    root.mkdir(parents=True)
    original = Persona(id="p_test", identity="Student", age_group="20s", gender="Female",
                       description="", intent="snack", purpose="snack")
    data = original.model_dump(mode="json")
    previous = json.dumps([data])
    (root / "personas.json").write_text(previous)
    (root / "metadata.json").write_text(json.dumps({"name": "Test", "updated_at": "original"}))

    response = TestClient(app).put("/api/projects/proj_test/personas", json={
        "personas": [data, {**data, "id": duplicate_id, "identity": "Different shopper"}],
    })

    assert response.status_code == 422
    assert (root / "personas.json").read_text() == previous
    assert json.loads((root / "metadata.json").read_text())["updated_at"] == "original"
