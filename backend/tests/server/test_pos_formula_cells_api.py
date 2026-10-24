"""Uncached POS formulas must fail before replacing analysis evidence."""

from unittest.mock import Mock

from fastapi.testclient import TestClient
import pytest

from store_emulator.application import simulation
from store_emulator.server.main import app
from tests.engine.test_pos_formula_cells import workbook
from tests.engine.test_pos_array_formula_cells import array_workbook


@pytest.mark.parametrize("column", ["sku", "quantity", "unit_price"])
@pytest.mark.parametrize("array", [False, True])
def test_unreadable_pos_cells_preserve_existing_reports(tmp_path, monkeypatch, column, array):
    monkeypatch.chdir(tmp_path)
    base = tmp_path / "run"
    output = base / "output"
    output.mkdir(parents=True)
    saved = output / "fidelity.json"
    before = b'{"previous_evidence": true}\n'
    saved.write_bytes(before)
    monkeypatch.setattr(simulation, "_completed_run_base", lambda *_: base)
    load_store = Mock(side_effect=AssertionError("Uncached formulas must fail before analysis"))
    monkeypatch.setattr(simulation, "load_run_store", load_store)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post("/api/projects/proj_test/runs/run_test/fidelity", files={
            "file": ("pos.xlsx", array_workbook(column) if array else workbook(column, "=1+1"),
                     "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        })
    assert response.status_code == 400, response.text
    assert "formula without a saved result" in response.json()["detail"]
    assert saved.read_bytes() == before
    load_store.assert_not_called()
