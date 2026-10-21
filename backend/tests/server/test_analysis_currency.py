"""Analysis jobs keep the currency of the saved shopper budgets and shelf prices."""

from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from store_emulator.application.storage.io import read_json, write_json
from store_emulator.application.storage.setups import metadata_path, setup_path
from store_emulator.domain.capture import CaptureResult
from store_emulator.domain.town import Town

PID = "proj_67916afd"
SID = "setup_7d6d"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    with TestClient(app) as client:
        yield client


def set_currencies(budget, store):
    path = metadata_path(PID)
    write_json(path, {**read_json(path), "currency": budget})
    path = setup_path(PID, SID)
    setup = read_json(path)
    setup["store"]["currency"] = store
    write_json(path, setup)


@pytest.mark.parametrize("budget,store,status", [("JPY", "JPY", 200), ("KRW", None, 200), ("USD", "KRW", 422)])
def test_synergy_uses_project_currency_before_model_setup(client, monkeypatch, budget, store, status):
    from store_emulator.application import town_synergy
    set_currencies(budget, store)
    town = Town.model_validate({"id": "town_test", "name": "Test", "archetype": "residential", "size_m": 200,
        "focal_venue_id": "focal", "venues": [{"id": "cafe", "name": "Cafe", "category": "cafe", "x": 100, "y": 100}]})
    monkeypatch.setattr(town_synergy, "require_town", lambda _pid: town)
    submit = Mock()
    resolve = Mock()
    monkeypatch.setattr(town_synergy.executor, "submit", submit)
    monkeypatch.setattr(town_synergy, "ensure_resolvable", resolve)
    response = client.post(f"/api/projects/{PID}/town/venues/cafe/synergy-vlm", json={"setup_id": SID})
    assert response.status_code == status, response.text
    if status == 422:
        resolve.assert_not_called()
        submit.assert_not_called()
        assert town_synergy.list_synergy_jobs(PID) == []
    else:
        assert submit.call_args.args[-1].currency == budget
        assert resolve.call_args.args[0].currency == budget


@pytest.mark.parametrize("budget,store,capture,status", [
    ("JPY", "JPY", "JPY", 200), ("KRW", None, "KRW", 200),
    ("USD", "KRW", "KRW", 422), ("USD", "USD", "JPY", 422),
])
def test_audit_does_not_mix_currency_units(client, monkeypatch, budget, store, capture, status):
    from store_emulator.application import shelf_lab
    set_currencies(budget, store)
    result = CaptureResult(image_size=(2, 2), currency=capture)
    monkeypatch.setattr(shelf_lab, "_photo_and_result", lambda *_: (Image.new("RGB", (2, 2)), result))
    submit = Mock()
    evaluator = Mock(wraps=shelf_lab.LayoutEvaluator)
    monkeypatch.setattr(shelf_lab.executor, "submit", submit)
    monkeypatch.setattr(shelf_lab, "LayoutEvaluator", evaluator)
    response = client.post(f"/api/projects/{PID}/captures/cap_test/audit", json={
        "setup_id": SID, "rack_id": "r_b5cf7836", "panel": 20, "max_stockouts": 0,
    })
    assert response.status_code == status, response.text
    if status == 422:
        submit.assert_not_called()
        assert shelf_lab.list_jobs(PID, "cap_test") == []
    else:
        submit.call_args.args[0]()
        view = shelf_lab.get_job(PID, "cap_test", response.json()["job_id"])
        assert view.status.status == "completed", view.status.error
        assert evaluator.call_args.args[0].currency == budget
        assert view.audit is not None
        assert view.audit.currency == budget
