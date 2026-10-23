"""Template currency survives execution; mixed budget units fail before jobs start."""

import pytest
from fastapi.testclient import TestClient

from store_emulator.application.storage.io import read_json, write_json
from store_emulator.application.storage.setups import metadata_path

PID = "proj_67916afd"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from store_emulator.server.main import app
    with TestClient(app) as client:
        yield client


def test_currency_mismatch_starts_no_run_or_experiment(client, monkeypatch):
    from store_emulator.application.async_executor import executor
    from unittest.mock import Mock
    submit = Mock()
    monkeypatch.setattr(executor, "submit", submit)
    sid = client.post(f"/api/projects/{PID}/setups/generate", json={"template_id": "specialty_cafe", "currency": "JPY"}).json()["id"]
    before = client.get(f"/api/projects/{PID}/setups/{sid}").json()
    response = client.post(f"/api/projects/{PID}/runs", json={"setup_id": sid, "engine_type": "rule_based", "preview": True})
    assert response.status_code == 422, response.text
    assert "shopper budgets use USD" in response.json()["detail"]
    store = before["store"]
    sku = next(i["sku"] for r in store["racks"] for s in r["slots"] for i in s["items"])
    experiment = client.post(f"/api/projects/{PID}/experiments", json={"setup_id": sid,
        "variants": [{"name": "Discount", "changes": [{"kind": "discount", "sku": sku, "percent": -20}]}]})
    assert experiment.status_code == 422
    assert client.get(f"/api/projects/{PID}/setups/{sid}").json() == before
    submit.assert_not_called()


@pytest.mark.parametrize("currency", ["KRW", "JPY"])
def test_matching_currency_survives_summary_and_saved_run_config(client, currency):
    from store_emulator.application.config import local_config
    from store_emulator.application.simulation import RunOptions, prepare_simulation, run_simulation_background
    from store_emulator.domain.config import EngineType
    path = metadata_path(PID)
    write_json(path, {**read_json(path), "currency": currency})
    sid = client.post(f"/api/projects/{PID}/setups/generate", json={"template_id": "specialty_cafe", "currency": currency}).json()["id"]
    rid, store, personas, address, profile, _ = prepare_simulation(PID, sid, preview=True, default_currency="USD")
    config = local_config().model_copy(update={"currency": "USD"})
    run_simulation_background(PID, rid, sid, store, personas, config, address, profile,
                              RunOptions(engine_type=EngineType.RULE_BASED, max_customers=10, preview=True))
    status = client.get(f"/api/projects/{PID}/runs/{rid}/status").json()
    assert status["status"] == "completed", status
    result = client.get(f"/api/projects/{PID}/runs/{rid}/summary").json()
    assert result["summary"]["currency"] == currency
    base = path.parent / "runs" / rid / "input"
    assert read_json(base / "config.json")["currency"] == currency
    assert read_json(base / "store.json")["currency"] == currency
    assert config.currency == "USD"


def test_legacy_store_inherits_project_budget_currency(client):
    from store_emulator.application.currencies import simulation_currency
    from store_emulator.domain.store import Store
    path = metadata_path(PID)
    write_json(path, {**read_json(path), "currency": "KRW"})
    store = Store.model_validate(client.get(f"/api/projects/{PID}/setups/setup_7d6d").json()["store"])
    assert store.currency is None
    assert simulation_currency(PID, store, "USD") == "KRW"


def test_receipt_review_uses_template_currency(client):
    sid = client.post(f"/api/projects/{PID}/setups/generate", json={"template_id": "specialty_cafe", "currency": "JPY"}).json()["id"]
    store = client.get(f"/api/projects/{PID}/setups/{sid}").json()["store"]
    item = next(i for r in store["racks"] for s in r["slots"] for i in s["items"])
    result = client.post(f"/api/projects/{PID}/receipts/review", json={"setup_id": sid, "receipts": [{"receipt_id": "r1", "currency": "JPY", "lines": [
        {"name": item["name"], "sku": item["sku"], "quantity": 1, "unit_price": item["price"]},
    ]}]}).json()
    assert result["ready"] and result["currency"] == "JPY"


def test_older_template_layout_recovers_currency_from_provenance_without_rewriting(client):
    from store_emulator.application.storage.setups import setup_path
    sid = client.post(f"/api/projects/{PID}/setups/generate", json={"template_id": "specialty_cafe", "currency": "KRW"}).json()["id"]
    path = setup_path(PID, sid)
    saved = read_json(path)
    del saved["store"]["currency"]
    write_json(path, saved)
    assert client.get(f"/api/projects/{PID}/setups/{sid}").json()["store"]["currency"] == "KRW"
    assert "currency" not in read_json(path)["store"]
