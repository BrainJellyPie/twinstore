"""Photo inputs through the API: a storefront photo sets the store's pull in the neighborhood."""

import io

import pytest
from fastapi.testclient import TestClient

from tests.engine.test_vision_inputs import storefront

PID = "proj_67916afd"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    with TestClient(app) as c:
        yield c


def _png(bright: bool) -> bytes:
    buf = io.BytesIO()
    storefront(bright).save(buf, format="PNG")
    return buf.getvalue()


def test_storefront_sets_venue_pull(client):
    town = client.post(f"/api/projects/{PID}/town/generate", json={"archetype": "residential", "seed": 1}).json()
    focal = town["focal_venue_id"]
    before = client.get(f"/api/projects/{PID}/town/demand").json()
    res = client.post(f"/api/projects/{PID}/town/venues/{focal}/storefront", files={"photo": ("front.png", _png(False), "image/png")},
                      data={"model": "none"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["appeal"]["method"] == "image_stats" and body["appeal"]["attractiveness"] < 1.0
    venue = next(v for v in body["town"]["venues"] if v["id"] == focal)
    assert venue["attractiveness"] == body["appeal"]["attractiveness"]
    after = client.get(f"/api/projects/{PID}/town/demand").json()
    assert after != before  # the demand model sees the new pull
    assert client.post(f"/api/projects/{PID}/town/venues/nope/storefront", files={"photo": ("f.png", _png(True), "image/png")}).status_code == 404


def test_receipts_need_a_vision_model(client):
    res = client.post(f"/api/projects/{PID}/receipts", files=[("photos", ("r.png", _png(True), "image/png"))], data={"model": "none"})
    assert res.status_code == 400
