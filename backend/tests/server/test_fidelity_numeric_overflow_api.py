"""Numeric overflow must not corrupt the last saved fidelity report."""

from contextlib import nullcontext
import json

from fastapi.testclient import TestClient
import pytest

from store_emulator.application import simulation
from store_emulator.server.main import app
from tests.engine.test_fidelity_numeric_overflow import OVERFLOW_ROWS, csv_data
from tests.engine.test_shared_store import _shopper, _store


@pytest.fixture
def completed_run(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    base = tmp_path / "run"
    output = base / "output"
    output.mkdir(parents=True)
    saved = output / "fidelity.json"
    saved.write_bytes(b'{"previous_evidence": true}\n')
    monkeypatch.setattr(simulation, "_completed_run_base", lambda *_: base)
    monkeypatch.setattr(simulation, "load_run_store", lambda _: _store())
    monkeypatch.setattr(simulation, "load_run_results", lambda _: [_shopper("p", "10:00:00", [("chips", 1)])])
    monkeypatch.setattr(simulation, "setup_tree_transaction", lambda _: nullcontext())
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, saved


@pytest.mark.parametrize("rows", OVERFLOW_ROWS)
def test_overflow_returns_400_without_replacing_saved_evidence(completed_run, rows):
    client, saved = completed_run
    before = saved.read_bytes()
    response = client.post("/api/projects/proj_test/runs/run_test/fidelity",
        files={"file": ("pos.csv", csv_data(rows), "text/csv")})
    assert response.status_code == 400, response.text
    assert "POS totals exceed" in response.json()["detail"]
    assert saved.read_bytes() == before


def test_unrepresentable_ratio_is_saved_as_null_and_matches_the_http_report(completed_run):
    client, saved = completed_run
    response = client.post("/api/projects/proj_test/runs/run_test/fidelity",
        files={"file": ("pos.csv", csv_data("r,chips,1,1e-310\n"), "text/csv")})
    assert response.status_code == 200, response.text
    report = response.json()
    assert next(metric["value"] for metric in report["metrics"] if metric["name"] == "basket_value_mean_ratio") is None
    assert json.loads(saved.read_bytes()) == report
    json.dumps(report, allow_nan=False)
