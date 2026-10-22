"""Shelf face photos through HTTP: the status the browser renders from, uploads checked against the layout,
and keys that match the store a vision run actually uses."""

import base64
import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from store_emulator.application import simulation as sim_service
from store_emulator.application.scenarios import prepare_inputs
from store_emulator.application.simulation import RunOptions, apply_options
from store_emulator.application.storage.setups import read_setup, write_setup
from store_emulator.domain.config import EngineType, SimulationConfig
from store_emulator.domain.types import Face
from store_emulator.engine.perception.shelf_photo import face_key

PID, SID = "proj_67916afd", "setup_eaf5"
URL = f"/api/projects/{PID}/setups/{SID}/shelf-views"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TWINSTORE_LOCAL_VLM_AUTO", "0")
    from store_emulator.server.main import app
    with TestClient(app) as c:
        yield c


def _data_url(size: tuple[int, int] = (480, 360), fmt: str = "JPEG") -> str:
    buf = io.BytesIO()
    Image.new("RGB", size, (200, 180, 150)).save(buf, format=fmt)
    mime = "jpeg" if fmt == "JPEG" else "png"
    return f"data:image/{mime};base64," + base64.b64encode(buf.getvalue()).decode()


def test_status_upload_and_stale_rejection(client: TestClient):
    status = client.get(URL)
    assert status.status_code == 200, status.text
    body = status.json()
    faces = body["faces"]
    assert faces and not any(f["ready"] for f in faces)
    assert body["store"]["racks"] and body["currency"]
    first = faces[0]
    upload = {"rack_id": first["rack_id"], "face": first["face"], "image": _data_url(),
              "boxes": {f"{first['face']}:4:0:0": [[10, 20, 100, 200]]}}
    saved = client.put(f"{URL}/{first['key']}", json=upload)
    assert saved.status_code == 200, saved.text
    assert saved.json()["ready"] is True
    again = client.get(URL).json()["faces"]
    assert [f["ready"] for f in again] == [True] + [False] * (len(again) - 1)

    # A key from before an edit, another rack's key, a non-picture and an unknown face are refused.
    assert client.put(f"{URL}/{'0' * 64}", json=upload).status_code == 409
    other = faces[1]
    assert client.put(f"{URL}/{other['key']}", json=upload).status_code == 409
    bad = client.put(f"{URL}/{first['key']}", json={**upload, "image": "data:image/gif;base64,R0lGODlh"})
    assert bad.status_code in (409, 422)
    assert client.put(f"{URL}/{first['key']}", json={**upload, "image": _data_url((32, 32), "PNG")}).status_code == 422
    assert client.put(f"{URL}/{first['key']}", json={**upload, "rack_id": "no-such-rack"}).status_code == 409

    # Editing the rack changes its key: the old photo is no longer ready.
    setup = read_setup(PID, SID)
    rack = next(r for r in setup["store"]["racks"] if r["id"] == first["rack_id"])
    slot = next(s for s in rack["slots"] if s["face"] == first["face"] and s["items"])
    slot["items"][0]["price"] += 10
    write_setup(PID, SID, setup)
    edited = next(f for f in client.get(URL).json()["faces"] if f["rack_id"] == first["rack_id"] and f["face"] == first["face"])
    assert edited["key"] != first["key"] and edited["ready"] is False


def test_keys_match_the_store_a_vision_run_uses(client: TestClient):
    faces = client.get(URL).json()["faces"]
    config = apply_options(SimulationConfig(engine_type=EngineType.VLM_GLANCE), RunOptions(shelf_view="photo_chart"))
    assert config.engines.vlm_glance.shelf_view == "photo_chart"
    _, store, personas, _, _ = sim_service.prepare_simulation(PID, SID, preview=True, default_currency=config.currency)
    config = config.model_copy(update={"currency": store.currency or config.currency})
    run_store, _ = prepare_inputs(config, store, personas)
    racks = {r.id: r for r in run_store.product_racks}
    for f in faces:
        assert face_key(racks[f["rack_id"]], Face(f["face"]), config.currency) == f["key"]
