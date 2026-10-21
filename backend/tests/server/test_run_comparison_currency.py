"""Historical runs must use the same monetary unit before they can be compared."""

import pytest
from fastapi.testclient import TestClient

from store_emulator.application.storage.io import write_json
from store_emulator.domain.customer import CustomerResult
from store_emulator.domain.types import Weekday


@pytest.fixture
def runs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    root = tmp_path / ".data" / "proj_test"
    write_json(root / "metadata.json", {"currency": "JPY"})
    for run_id in ("run_a", "run_b"):
        customer = CustomerResult(persona_id="p1", day=Weekday.MON,
                                  arrival_time="12:00:00", total_spent=100)
        write_json(root / "runs" / run_id / "output" / "timeline.json",
                   [customer.model_dump(mode="json")])
    from store_emulator.server.main import app
    return TestClient(app, raise_server_exceptions=False), root


@pytest.mark.parametrize("source", ["output/summary.json", "input/config.json", "input/store.json"])
@pytest.mark.parametrize("currency_a,currency_b", [("USD_CENTS", "KRW"), ("JPY", "USD")])
def test_rejects_different_saved_currencies(runs, source, currency_a, currency_b):
    client, root = runs
    for run_id, currency in (("run_a", currency_a), ("run_b", currency_b)):
        write_json(root / "runs" / run_id / source, {"currency": currency})
    before = {p.relative_to(root): p.read_bytes() for p in root.rglob("*.json")}

    response = client.get("/api/projects/proj_test/compare?a=run_a&b=run_b&n_bootstrap=200")

    assert response.status_code == 422, response.text
    assert currency_a.replace("_CENTS", "") in response.json()["detail"]
    assert currency_b in response.json()["detail"]
    assert {p.relative_to(root): p.read_bytes() for p in root.rglob("*.json")} == before


@pytest.mark.parametrize("source,currency_a,currency_b,expected", [
    ("output/summary.json", "KRW", "KRW", "KRW"),
    ("output/summary.json", " usd_cents ", "USD", "USD"),
    ("input/config.json", "KRW", "KRW", "KRW"),
    ("input/store.json", "JPY", "JPY", "JPY"),
    ("output/summary.json", None, None, "USD"),
])
def test_compares_matching_historical_units_independently_of_current_project(runs, source, currency_a, currency_b, expected):
    client, root = runs
    for run_id, currency in (("run_a", currency_a), ("run_b", currency_b)):
        if currency is not None:
            write_json(root / "runs" / run_id / source, {"currency": currency})
        if source == "output/summary.json" and currency == "KRW":
            write_json(root / "runs" / run_id / "input" / "config.json", {"currency": "USD"})

    response = client.get("/api/projects/proj_test/compare?a=run_a&b=run_b&n_bootstrap=200")

    assert response.status_code == 200, response.text
    report = response.json()
    assert report["paired_customers"] == 1
    assert report["metrics"][0]["mean_a"] == 100
    assert any(expected in note and "minor unit" in note for note in report["notes"])
