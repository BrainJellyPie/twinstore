"""Feature endpoints accept the same safe IDs as the project API."""
import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from store_emulator.application.storage.io import write_json
from store_emulator.application.storage.setups import new_setup_data


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.parametrize("pid", ["Project-A", "proj_UPPER", "project-with-hyphen", "proj_lower"])
@pytest.mark.parametrize("feature", ["setup_save", "captures", "packages", "floorplan", "receipts"])
def test_feature_routes_accept_project_ids(client, tmp_path, pid, feature):
    root = tmp_path / ".data" / pid
    write_json(root / "metadata.json", {"name": "Test", "currency": "USD"})
    if feature == "setup_save":
        setup = new_setup_data("Source", None, None)
        setup["id"] = "setup_test"
        write_json(root / "setups" / "setup_test.json", setup)
        response = client.put(f"/api/projects/{pid}/setups/setup_test", json={"setup": {"name": "Renamed"}})
    elif feature == "captures":
        response = client.get(f"/api/projects/{pid}/captures")
    elif feature == "packages":
        response = client.get(f"/api/projects/{pid}/lab/packages")
    elif feature == "floorplan":
        data = io.BytesIO()
        Image.new("RGB", (64, 64), "white").save(data, format="PNG")
        response = client.post(f"/api/projects/{pid}/floorplan/preview", files={"plan": ("plan.png", data.getvalue(), "image/png")})
    else:
        response = client.post(f"/api/projects/{pid}/receipts/review", json={"receipts": []})
    assert response.status_code == 200, response.text


@pytest.mark.parametrize("sid", ["Setup-A", "setup_UPPER", "setup-with-hyphen"])
def test_setup_save_accepts_safe_setup_ids(client, tmp_path, sid):
    root = tmp_path / ".data" / "proj_test"
    write_json(root / "metadata.json", {"name": "Test", "currency": "USD"})
    setup = new_setup_data("Source", None, None)
    setup["id"] = sid
    write_json(root / "setups" / f"{sid}.json", setup)
    response = client.put(f"/api/projects/proj_test/setups/{sid}", json={"setup": {"name": "Renamed"}})
    assert response.status_code == 200, response.text
    assert response.json()["setup"]["name"] == "Renamed"


@pytest.mark.parametrize("resource", ["capture", "package", "run"])
def test_safe_missing_nested_ids_are_reported_as_not_found(client, tmp_path, resource):
    write_json(tmp_path / ".data" / "proj_test" / "metadata.json", {"currency": "USD"})
    if resource == "capture":
        response = client.get("/api/projects/proj_test/captures/Capture-A")
    elif resource == "package":
        response = client.get("/api/projects/proj_test/lab/packages/Package-A")
    else:
        response = client.post("/api/projects/proj_test/receipts/review", json={"receipts": [], "run_id": "Run-A"})
    assert response.status_code == 404, response.text
