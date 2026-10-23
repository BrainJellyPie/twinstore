"""Long result analyses must leave unrelated requests on the same server loop responsive."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from threading import Event

import pytest
from fastapi.testclient import TestClient

from store_emulator.application import simulation
from store_emulator.application.errors import AppError
from store_emulator.domain.analysis import ComparisonReport, FidelityReport
from store_emulator.server.main import app


@pytest.mark.parametrize("operation", ["compare", "fidelity", "export"])
@pytest.mark.parametrize("missing", [False, True])
def test_analysis_leaves_health_available_and_keeps_the_original_response(monkeypatch, operation, missing):
    @asynccontextmanager
    async def no_startup(_app):
        yield

    monkeypatch.setattr(app.router, "lifespan_context", no_startup)
    started, release = Event(), Event()
    method = {"compare": "compare_project_runs", "fidelity": "run_fidelity", "export": "export_customers_csv"}[operation]
    received = []

    def calculate(*args, **kwargs):
        received.append((args, kwargs))
        started.set()
        assert release.wait(5), "analysis was not released"
        if missing:
            raise FileNotFoundError("offline missing run")
        if operation == "compare":
            return ComparisonReport(run_a="run_a", run_b="run_b", paired_customers=0, unpaired_a=0,
                                    unpaired_b=0, n_bootstrap=200, confidence=0.95, metrics=[])
        if operation == "fidelity":
            return FidelityReport(sim_customers=1, real_transactions=1, matched_skus=1, metrics=[])
        return "id,name\np,고객\n"

    monkeypatch.setattr(simulation, method, calculate)
    with TestClient(app) as client, ThreadPoolExecutor(max_workers=2) as pool:
        if operation == "compare":
            pending = pool.submit(client.get, "/api/projects/proj_test/compare?a=run_a&b=run_b&n_bootstrap=200")
        elif operation == "fidelity":
            pending = pool.submit(client.post, "/api/projects/proj_test/runs/run_a/fidelity",
                                  files={"file": ("실제매출.csv", b"receipt_id,sku\nr,tea\n", "text/csv")})
        else:
            pending = pool.submit(client.get, "/api/projects/proj_test/runs/run_a/export.csv")
        try:
            assert started.wait(5)
            response = pool.submit(client.get, "/api/health").result(timeout=1)
            assert response.json() == {"status": "ok"}
            assert not pending.done()
        finally:
            release.set()
        response = pending.result(timeout=5)
    assert response.status_code == (404 if missing else 200), response.text
    if missing:
        assert response.json()["detail"] == "offline missing run"
    elif operation == "export":
        assert response.text == "\ufeffid,name\np,고객\n"
        assert 'filename="proj_test_run_a_customers.csv"' in response.headers["content-disposition"]
    elif operation == "compare":
        assert response.json()["run_b"] == "run_b"
        assert received == [(("proj_test", "run_a", "run_b"), {"n_bootstrap": 200})]
    else:
        assert response.json()["real_transactions"] == 1
        assert received == [(("proj_test", "run_a", b"receipt_id,sku\nr,tea\n", "실제매출.csv"), {})]


@pytest.mark.parametrize("operation", ["compare", "fidelity"])
def test_analysis_keeps_application_error_status(monkeypatch, operation):
    def fail(*args, **kwargs):
        raise AppError("offline invalid input", 422)

    monkeypatch.setattr(simulation, "compare_project_runs" if operation == "compare" else "run_fidelity", fail)
    client = TestClient(app)
    response = client.get("/api/projects/proj_test/compare?a=run_a&b=run_b") if operation == "compare" else client.post(
        "/api/projects/proj_test/runs/run_a/fidelity", files={"file": ("pos.csv", b"invalid")})
    assert response.status_code == 422 and response.json()["detail"] == "offline invalid input"
