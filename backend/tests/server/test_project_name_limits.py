"""A store's name is required and at most 200 characters, both when the store is created and when it is renamed."""

import json

from fastapi.testclient import TestClient

from store_emulator.server.main import app

DAYS = [{"day": d, "is_open": True, "open_time": "08:00", "close_time": "20:00"} for d in range(7)]


def _meta(name: str) -> dict[str, object]:
    return {"name": name, "address": "1 Main St", "store_type": "Convenience store", "customer_profile": "Commuters",
            "weekly_schedule": DAYS}


def test_rename_rejects_blank_and_overlong_names_and_keeps_the_old_one(tmp_path, monkeypatch):
    from store_emulator.application.storage import setups

    monkeypatch.setattr(setups, "DATA_DIR", str(tmp_path))
    pid = "proj_names"
    meta = tmp_path / pid / "metadata.json"
    meta.parent.mkdir()
    meta.write_text(json.dumps({"project_id": pid, "name": "Corner shop"}))
    api = TestClient(app)
    for name in ["", "   ", "x" * 201]:
        assert api.put(f"/api/projects/{pid}/metadata", json={"name": name}).status_code == 422
    assert json.loads(meta.read_text())["name"] == "Corner shop"
    assert api.put(f"/api/projects/{pid}/metadata", json={"name": "x" * 200}).status_code == 200
    assert api.put(f"/api/projects/{pid}/metadata", json={"description": "No rename"}).status_code == 200
    assert json.loads(meta.read_text())["name"] == "x" * 200


def test_create_rejects_an_overlong_name():
    response = TestClient(app).post("/api/projects/create-store", data={"meta": json.dumps(_meta("x" * 201))})
    assert response.status_code == 422
