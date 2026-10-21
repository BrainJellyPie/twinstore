"""Floor plan import through the API: a sketch becomes a new active draft layout."""

import io
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))
from test_floorplan import sketch

PID = "proj_67916afd"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    with TestClient(app) as c:
        yield c


def _png() -> bytes:
    buf = io.BytesIO()
    sketch(seed=1).save(buf, format="PNG")
    return buf.getvalue()


def test_sketch_becomes_a_layout(client):
    res = client.post(f"/api/projects/{PID}/floorplan", files={"plan": ("my-store.png", _png(), "image/png")},
                      data={"reader": "auto", "model": "none"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["reading"]["reader"] == "classic" and body["racks"] > 5
    assert body["setup"]["name"] == "floor plan (my-store)"
    setup = client.get(f"/api/projects/{PID}/setups/{body['setup_id']}").json()
    assert setup["store"]["grid_size"] == list(body["grid_size"])
    assert client.get(f"/api/projects/{PID}").json()["state"]["activeSetupId"] == body["setup_id"]


def test_bad_uploads_are_rejected(client):
    assert client.post(f"/api/projects/{PID}/floorplan", files={"plan": ("x.png", b"not an image", "image/png")}).status_code == 400
    pdf = client.post(f"/api/projects/{PID}/floorplan", files={"plan": ("plan.pdf", b"%PDF-1.4 ...", "application/pdf")})
    assert pdf.status_code in (400, 422)
    assert client.post("/api/projects/nope/floorplan", files={"plan": ("x.png", _png(), "image/png")}).status_code == 404
