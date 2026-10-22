"""Shelf Lab through the API: package upload, counterfactual edits with masks, audit job; sim2real needs
products the model has read."""

import io
import time

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from store_emulator.engine.capture.synthetic import make_scene
from store_emulator.engine.layout_gen.templates import generate_store
from store_emulator.engine.shelf_lab.edits import synth_package

PID = "proj_67916afd"
SETUP = "setup_7d6d"
DRINK_1 = "r_b5cf7836"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    with TestClient(app) as c:
        yield c


def _png(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _capture(client) -> tuple[str, dict]:
    store = generate_store("urban_cvs", seed=1)
    rack = [r for r in store.racks if r.slots][2]
    scene = make_scene(rack, rack.slots[0].face, currency="USD", seed=21, severity="mild")
    files = {"image": ("shelf.png", _png(scene.image), "image/png")}
    started = client.post(f"/api/projects/{PID}/captures", files=files, data={"detector": "classic", "model": "none", "rack_type": "fridge"})
    assert started.status_code == 200, started.text
    cid = started.json()["capture_id"]
    for _ in range(600):
        view = client.get(f"/api/projects/{PID}/captures/{cid}").json()
        if view["status"]["status"] in ("completed", "failed"):
            assert view["status"]["status"] == "completed", view["status"]["error"]
            return cid, view["result"]
        time.sleep(0.1)
    raise AssertionError("capture did not finish")


def _wait_job(client, cid: str, jid: str) -> dict:
    for _ in range(1200):
        view = client.get(f"/api/projects/{PID}/captures/{cid}/lab/jobs/{jid}").json()
        if view["status"]["status"] in ("completed", "failed"):
            return view
        time.sleep(0.1)
    raise AssertionError("lab job did not finish")


def test_edits_packages_and_audit(client):
    cid, result = _capture(client)
    items = result["items"]

    pkg = client.post(f"/api/projects/{PID}/lab/packages", files={"image": ("volt.png", _png(synth_package("Volt Cola")), "image/png")})
    assert pkg.status_code == 200, pkg.text
    aid = pkg.json()["asset_id"]
    assert [p["asset_id"] for p in client.get(f"/api/projects/{PID}/lab/packages").json()] == [aid]
    assert client.get(f"/api/projects/{PID}/lab/packages/{aid}").content[:4] == b"\x89PNG"

    edits = [
        {"kind": "remove", "item_id": items[0]["id"]},
        {"kind": "replace", "item_id": items[1]["id"], "name": "Volt Cola", "asset_id": aid, "price": 199},
        {"kind": "promo", "item_id": items[2]["id"], "promo": "1+1"},
    ]
    made = client.post(f"/api/projects/{PID}/captures/{cid}/edits", json={"edits": edits})
    assert made.status_code == 200, made.text
    shelf = made.json()
    eid = shelf["edit_id"]
    assert {c["kind"] for c in shelf["changes"]} == {"remove", "replace", "promo"}
    assert shelf["promos"] == {items[2]["id"]: "1+1"}
    assert items[0]["id"] not in {i["id"] for i in shelf["result"]["items"]}
    image = client.get(f"/api/projects/{PID}/captures/{cid}/edits/{eid}/image")
    mask = client.get(f"/api/projects/{PID}/captures/{cid}/edits/{eid}/mask")
    assert image.headers["content-type"] == "image/jpeg" and mask.content[:4] == b"\x89PNG"
    m = Image.open(io.BytesIO(mask.content))
    assert m.size == tuple(shelf["image_size"]) and m.getextrema() == (0, 255)
    assert [e["edit_id"] for e in client.get(f"/api/projects/{PID}/captures/{cid}/edits").json()] == [eid]

    bad = client.post(f"/api/projects/{PID}/captures/{cid}/edits", json={"edits": [{"kind": "remove", "item_id": "i99"}]})
    assert bad.status_code == 400
    # Nothing was read by a model: sim2real has no product names to compare.
    assert client.post(f"/api/projects/{PID}/captures/{cid}/sim2real", json={}).status_code == 409

    # A side of the rack with nothing planned on it is refused (it scored 100 % compliant, every product "unexpected").
    rack = next(r for r in client.get(f"/api/projects/{PID}/setups/{SETUP}").json()["store"]["racks"] if r["id"] == DRINK_1)
    empty_side = next(f for f in "NSEW" if f not in {slot["face"] for slot in rack["slots"] if slot["items"]})
    refused = client.post(f"/api/projects/{PID}/captures/{cid}/audit",
                          json={"setup_id": SETUP, "rack_id": DRINK_1, "face": empty_side, "panel": 40})
    assert refused.status_code == 400 and "holds no products" in refused.json()["detail"]

    started = client.post(f"/api/projects/{PID}/captures/{cid}/audit",
                          json={"setup_id": SETUP, "rack_id": DRINK_1, "edit_id": eid, "panel": 40, "max_stockouts": 2})
    assert started.status_code == 200, started.text
    view = _wait_job(client, cid, started.json()["job_id"])
    assert view["status"]["status"] == "completed", view["status"]["error"]
    report = view["audit"]
    assert report["rack_id"] == DRINK_1 and report["face"] in "NSEW" and 0.0 <= report["compliance"] <= 1.0
    assert report["levels"] and report["panel_size"] == 40 and report["impact"] is not None
    priced = [f for f in report["findings"] if f["kind"] == "missing" and f["loss_per_day"] is not None]
    assert 1 <= len(priced) <= 2

    assert client.delete(f"/api/projects/{PID}/captures/{cid}/edits/{eid}").status_code == 204
    assert client.get(f"/api/projects/{PID}/captures/{cid}/edits/{eid}").status_code == 404
