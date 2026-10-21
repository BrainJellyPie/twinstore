"""Captured shelf comparisons and saved layouts must not silently mix money units."""

from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from store_emulator.application.storage.io import read_json, write_json
from store_emulator.application.storage.setups import metadata_path, setup_path
from store_emulator.domain.capture import CaptureItem, CaptureResult, CaptureStatus
from store_emulator.domain.config import LLMConfig

PID = "proj_67916afd"
SID = "setup_7d6d"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    with TestClient(app) as client:
        yield client


def captured_product(currency, item):
    return CaptureResult(image_size=(2, 2), currency=currency, items=[CaptureItem(
        id="i1", band=0, level=1, order=0, name=item["name"], sku=item["sku"], price=item["price"], labeled=True,
    )])


@pytest.mark.parametrize("budget,capture,status", [("USD", "JPY", 422), ("KRW", "USD", 422), ("KRW", "KRW", 200)])
def test_sim2real_rejects_incompatible_shopper_budgets(client, monkeypatch, budget, capture, status):
    from store_emulator.application import shelf_lab
    path = metadata_path(PID)
    write_json(path, {**read_json(path), "currency": budget})
    result = captured_product(capture, {"name": "Tea", "sku": "tea", "price": 2500})
    monkeypatch.setattr(shelf_lab, "_photo_and_result", lambda *_: (Image.new("RGB", (2, 2)), result))
    resolve = Mock(return_value=LLMConfig(model="fake"))
    submit = Mock()
    monkeypatch.setattr(shelf_lab, "capture_llm_config", resolve)
    monkeypatch.setattr(shelf_lab.executor, "submit", submit)
    response = client.post(f"/api/projects/{PID}/captures/cap_test/sim2real", json={})
    assert response.status_code == status, response.text
    if status == 422:
        resolve.assert_not_called()
        submit.assert_not_called()
        assert shelf_lab.list_jobs(PID, "cap_test") == []
    else:
        submit.assert_called_once()


@pytest.mark.parametrize("budget,store,capture,status", [
    ("USD", "USD", "JPY", 422), ("KRW", None, "USD", 422),
    ("USD", "JPY", "JPY", 200), ("KRW", None, "KRW", 200),
])
def test_rival_price_comparison_requires_matching_shelf_units(client, monkeypatch, budget, store, capture, status):
    from store_emulator.application import shelf_lab
    path = metadata_path(PID)
    write_json(path, {**read_json(path), "currency": budget})
    path = setup_path(PID, SID)
    setup = read_json(path)
    setup["store"]["currency"] = store
    write_json(path, setup)
    item = next(i for r in setup["store"]["racks"] for s in r["slots"] for i in s["items"])
    result = captured_product(capture, item)
    monkeypatch.setattr(shelf_lab, "_capture", lambda *_: (Image.new("RGB", (2, 2)), result))
    response = client.post(f"/api/projects/{PID}/captures/cap_test/rival", json={"setup_id": SID})
    assert response.status_code == status, response.text
    if status == 200:
        assert response.json()["comparison"]["price_index"] == 1.0


@pytest.mark.parametrize("budget,store,currencies,status", [
    ("USD", "USD", ["JPY"], 422), ("KRW", None, ["USD"], 422),
    ("USD", "USD", ["USD", "JPY"], 422), ("USD", "JPY", ["JPY"], 200),
    ("KRW", None, ["KRW"], 200),
])
def test_capture_application_preserves_layout_price_units(client, monkeypatch, budget, store, currencies, status):
    from store_emulator.application import capture
    path = metadata_path(PID)
    write_json(path, {**read_json(path), "currency": budget})
    path = setup_path(PID, SID)
    setup = read_json(path)
    setup["store"]["currency"] = store
    write_json(path, setup)
    item = next(i for r in setup["store"]["racks"] for s in r["slots"] for i in s["items"])
    results = {f"cap_{i}": captured_product(currency, item) for i, currency in enumerate(currencies)}
    monkeypatch.setattr(capture, "_read_status", lambda _pid, cid: CaptureStatus(capture_id=cid, status="completed"))
    monkeypatch.setattr(capture, "_read_result", lambda _pid, cid: results[cid])
    images = Mock()
    monkeypatch.setattr(capture, "_save_sku_images", images)
    before = client.get(f"/api/projects/{PID}").json()
    if len(results) == 1:
        response = client.post(f"/api/projects/{PID}/captures/cap_0/apply", json={"setup_id": SID, "new_rack": True})
    else:
        response = client.post(f"/api/projects/{PID}/captures/apply", json={"setup_id": SID, "capture_ids": list(results)})
    assert response.status_code == status, response.text
    if status == 422:
        images.assert_not_called()
        assert client.get(f"/api/projects/{PID}").json() == before
    else:
        saved = client.get(f"/api/projects/{PID}/setups/{response.json()['setup_id']}").json()
        assert saved["store"]["currency"] == (store or budget)
    assert read_json(path) == setup
