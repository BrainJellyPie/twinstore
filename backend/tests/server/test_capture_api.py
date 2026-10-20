"""Shelf capture through the API: upload, poll, correct, apply as a new layout."""

import io
import time

import pytest
from fastapi.testclient import TestClient

from store_emulator.engine.capture.synthetic import make_scene
from store_emulator.engine.layout_gen.templates import generate_store

PID = "proj_67916afd"
SETUP = "setup_7d6d"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    with TestClient(app) as c:
        yield c


def _shelf_png() -> bytes:
    store = generate_store("urban_cvs", seed=1)
    rack = [r for r in store.racks if r.slots][2]
    scene = make_scene(rack, rack.slots[0].face, currency="USD", seed=21, severity="mild")
    buf = io.BytesIO()
    scene.image.save(buf, format="PNG")
    return buf.getvalue()


def _wait(client, cid):
    for _ in range(600):
        view = client.get(f"/api/projects/{PID}/captures/{cid}").json()
        if view["status"]["status"] in ("completed", "failed"):
            return view
        time.sleep(0.1)
    raise AssertionError("capture did not finish")


def test_capture_upload_correct_apply(client):
    files = {"image": ("shelf.png", _shelf_png(), "image/png")}
    form = {"detector": "classic", "model": "none", "currency": "usd", "rack_type": "fridge"}
    started = client.post(f"/api/projects/{PID}/captures", files=files, data=form)
    assert started.status_code == 200, started.text
    status = started.json()
    assert status["status"] == "pending" and status["options"]["currency"] == "USD"
    cid = status["capture_id"]

    view = _wait(client, cid)
    assert view["status"]["status"] == "completed", view["status"]["error"]
    result = view["result"]
    assert [b["level"] for b in result["bands"]] == [4, 3, 2, 1]
    assert result["detector"] == "classic" and result["items"] and result["vlm_calls"] == 0
    assert view["status"]["facings"] == sum(i["facings"] for i in result["items"])
    assert [c["capture_id"] for c in client.get(f"/api/projects/{PID}/captures").json()] == [cid]

    photo = client.get(f"/api/projects/{PID}/captures/{cid}/image")
    overlay = client.get(f"/api/projects/{PID}/captures/{cid}/image?overlay=1")
    assert photo.status_code == 200 and photo.headers["content-type"] == "image/jpeg"
    assert overlay.status_code == 200 and overlay.content[:4] == b"\x89PNG"

    # Corrections: rename + price the first item, merge the second into it, delete the third, add one.
    items = result["items"]
    first, second, third = items[0], items[1], items[2]
    edits = [
        {"id": first["id"], "name": "Zero Cola", "size": "500ml", "category": "soft drink", "price": 229,
         "facings": first["facings"] + second["facings"], "merged_from": [second["id"]]},
        *[{"id": i["id"], "name": i["name"], "facings": i["facings"]} for i in items[3:]],
        {"name": "Ginger Ale", "size": "355ml", "facings": 2, "level": 1},
    ]
    corrected = client.put(f"/api/projects/{PID}/captures/{cid}", json={"items": edits})
    assert corrected.status_code == 200, corrected.text
    fixed = corrected.json()["result"]
    assert fixed["edited"] and len(fixed["items"]) == len(items) - 1
    head = fixed["items"][0]
    assert head["name"] == "Zero Cola" and head["price"] == 229 and not head["price_estimated"]
    assert head["category"] == "soft_drinks" and len(head["boxes"]) == len(first["boxes"]) + len(second["boxes"])
    added = fixed["items"][-1]
    assert added["name"] == "Ginger Ale" and added["price_estimated"] and added["price"] == 189
    assert third["id"] not in {i["id"] for i in fixed["items"]}
    bad = client.put(f"/api/projects/{PID}/captures/{cid}", json={"items": [{"id": "i99", "name": "x"}]})
    assert bad.status_code == 400

    # New rack on free floor → new draft layout, source untouched.
    applied = client.post(f"/api/projects/{PID}/captures/{cid}/apply", json={"setup_id": SETUP, "new_rack": True})
    assert applied.status_code == 200, applied.text
    body = applied.json()
    new_id = body["setup_id"]
    assert body["setup"]["parentId"] == SETUP and body["setup"]["status"] == "draft" and body["rack_ids"]
    setup = client.get(f"/api/projects/{PID}/setups/{new_id}").json()
    racks = {r["id"]: r for r in setup["store"]["racks"]}
    new_rack = racks[body["rack_ids"][0]]
    assert new_rack["type"] == "fridge" and new_rack["slots"]
    names = {i["name"] for s in new_rack["slots"] for i in s["items"]}
    assert "Zero Cola 500ml" in names
    assert client.get(f"/api/projects/{PID}/captures/{cid}").json()["status"]["applied_setup_ids"] == [new_id]

    # Replace a rack face.
    replaced = client.post(f"/api/projects/{PID}/captures/{cid}/apply",
                           json={"setup_id": SETUP, "rack_id": "r_b5cf7836", "face": "S"})
    assert replaced.status_code == 200, replaced.text
    rep_setup = client.get(f"/api/projects/{PID}/setups/{replaced.json()['setup_id']}").json()
    fridge = next(r for r in rep_setup["store"]["racks"] if r["id"] == "r_b5cf7836")
    assert "Zero Cola 500ml" in {i["name"] for s in fridge["slots"] for i in s["items"]}
    assert all(len(s["items"]) <= 4 for s in fridge["slots"])

    # Several photos → several new racks.
    second_cid = client.post(f"/api/projects/{PID}/captures", files=files, data=form).json()["capture_id"]
    assert _wait(client, second_cid)["status"]["status"] == "completed"
    many = client.post(f"/api/projects/{PID}/captures/apply", json={"capture_ids": [cid, second_cid], "setup_id": SETUP})
    assert many.status_code == 200, many.text
    assert len(many.json()["rack_ids"]) >= 2

    assert client.delete(f"/api/projects/{PID}/captures/{second_cid}").status_code == 204
    assert client.get(f"/api/projects/{PID}/captures/{second_cid}").status_code == 404


def test_capture_rejects_bad_input(client):
    bad = client.post(f"/api/projects/{PID}/captures", files={"image": ("x.png", b"not an image", "image/png")},
                      data={"detector": "classic", "model": "none"})
    assert bad.status_code == 422
    missing = client.post("/api/projects/proj_nope/captures", files={"image": ("x.png", _shelf_png(), "image/png")},
                          data={"model": "none"})
    assert missing.status_code == 404
    no_model = client.post(f"/api/projects/{PID}/captures", files={"image": ("x.png", _shelf_png(), "image/png")},
                           data={"detector": "vlm", "model": "none"})
    assert no_model.status_code == 400
    assert client.get(f"/api/projects/{PID}/captures/cap_nope").status_code == 404
    assert client.get(f"/api/projects/{PID}/captures/..%2Fsetups").status_code in (400, 404)
