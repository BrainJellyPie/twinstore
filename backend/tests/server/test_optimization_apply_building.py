"""An optimized layout is saved on the same building floor as the layout it came from."""
import pytest
from fastapi.testclient import TestClient
from store_emulator.application.setups import run_operations
from store_emulator.domain.operations import OperationsConfig

from store_emulator.application.optimize import OptimizationStatus
from store_emulator.application.storage.io import write_json
from store_emulator.application.storage.setups import (
    new_setup_data,
    read_setup,
    setup_path,
)
from store_emulator.domain.optimize import OptimizeResult, OptimizeSpec
from store_emulator.engine.layout_gen import generate_store


@pytest.mark.parametrize("configured", [False, True])
def test_the_optimized_layout_keeps_the_sources_floor_and_evaluated_operations(tmp_path, monkeypatch, configured):
    monkeypatch.chdir(tmp_path)
    pid, job, sid = "proj_test", "opt_test", "setup_src"
    root = tmp_path / ".data" / pid
    spec = OptimizeSpec(budget=1, eval_customers=10)
    store = generate_store("mini_mart")
    source = new_setup_data("Ground floor", None, store.model_dump(mode="json"))
    source["id"] = sid
    source["building"] = {"id": "building_1", "name": "Mall", "level": 1, "label": "Ground", "floor_count": 2}
    write_json(root / "metadata.json", {"currency": "USD"})
    source["operations"] = OperationsConfig(stock_per_facing=99).model_dump(mode="json")
    write_json(setup_path(pid, sid), source)
    operations = OperationsConfig(stock_per_facing=1, backroom_per_product=0, crew=2) if configured else None
    status = OptimizationStatus(job_id=job, setup_id=sid, status="completed", spec=spec, operations=operations)
    result = OptimizeResult(spec=spec, baseline_score=100, best_score=110, relative_improvement=.1, best_store=store,
                            applied_moves=["Move tea"], history=[], evaluations=1, seconds=0)
    write_json(root / "optimizations" / job / "status.json", status.model_dump(mode="json"))
    write_json(root / "optimizations" / job / "result.json", result.model_dump(mode="json"))
    from store_emulator.server.main import app
    response = TestClient(app).post(f"/api/projects/{pid}/optimizations/{job}/apply", json={"name": None})
    assert response.status_code == 200, response.text
    assert read_setup(pid, response.json()["id"])["building"] == source["building"]
    assert run_operations(pid, response.json()["id"], None, None) == operations
    assert read_setup(pid, sid) == source
