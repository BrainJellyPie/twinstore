"""An optimized layout is saved on the same building floor as the layout it came from."""
from fastapi.testclient import TestClient

from store_emulator.application.optimize import OptimizationStatus
from store_emulator.application.storage.io import write_json
from store_emulator.application.storage.setups import (
    new_setup_data,
    read_setup,
    setup_path,
)
from store_emulator.domain.optimize import OptimizeResult, OptimizeSpec
from store_emulator.engine.layout_gen import generate_store


def test_the_optimized_layout_keeps_the_sources_floor(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    pid, job, sid = "proj_test", "opt_test", "setup_src"
    root = tmp_path / ".data" / pid
    spec = OptimizeSpec(budget=1, eval_customers=10)
    store = generate_store("mini_mart")
    source = new_setup_data("Ground floor", None, store.model_dump(mode="json"))
    source["id"] = sid
    source["building"] = {"id": "building_1", "name": "Mall", "level": 1, "label": "Ground", "floor_count": 2}
    write_json(root / "metadata.json", {"currency": "USD"})
    write_json(setup_path(pid, sid), source)
    status = OptimizationStatus(job_id=job, setup_id=sid, status="completed", spec=spec)
    result = OptimizeResult(spec=spec, baseline_score=100, best_score=110, relative_improvement=.1, best_store=store,
                            applied_moves=["Move tea"], history=[], evaluations=1, seconds=0)
    write_json(root / "optimizations" / job / "status.json", status.model_dump(mode="json"))
    write_json(root / "optimizations" / job / "result.json", result.model_dump(mode="json"))
    from store_emulator.server.main import app
    response = TestClient(app).post(f"/api/projects/{pid}/optimizations/{job}/apply", json={"name": None})
    assert response.status_code == 200, response.text
    assert read_setup(pid, response.json()["id"])["building"] == source["building"]
