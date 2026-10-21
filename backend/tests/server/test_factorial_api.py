import csv
import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from store_emulator.domain.customer import CustomerResult, TimelineEvent
from store_emulator.domain.types import Action

PID = "proj_67916afd"
SETUP = "setup_7d6d"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TWINSTORE_LOCAL_VLM_AUTO", "0")
    from store_emulator.server.main import app
    with TestClient(app) as client:
        yield client


def start_fixture(client, monkeypatch, missing_sign=False):
    from store_emulator.application import marketing
    async def outcomes(self, store, panel):
        item = next(i for r in store.racks for s in r.slots for i in s.items if i.sku == "A0001")
        a, b = int(item.price == 149), int(item.promo == "SALE")
        amount = 100 + 2 * a + 3 * b + 7 * a * b
        selected = panel[1:] if missing_sign and b and not a else panel
        return [CustomerResult(persona_id=p.id, day=p.day, arrival_time=f"{p.arrival_hour:02}:00", total_spent=amount,
            timeline=[TimelineEvent(elapsed_sec=1, x=0, y=0, action=Action.BUY, product_sku="A0001", price=amount)]) for p in selected]
    monkeypatch.setattr(marketing.LayoutEvaluator, "evaluate_customers", outcomes)
    monkeypatch.setattr(marketing.executor, "submit", lambda fn: fn())
    price = {"kind": "price", "sku": "A0001", "price": 149}
    sign = {"kind": "promo", "sku": "A0001", "promo": "SALE"}
    response = client.post(f"/api/projects/{PID}/experiments", json={"setup_id": SETUP, "panel": 40,
        "variants": [{"name": "Price", "changes": [price]}, {"name": "Sign", "changes": [sign]},
            {"name": "Both", "changes": [price, sign]}]})
    assert response.status_code == 200 and response.json()["status"] == "completed", response.text
    eid = response.json()["job_id"]
    root = f"/api/projects/{PID}/experiments/{eid}/factorial"
    source = client.get(root + "/source")
    assert source.status_code == 200 and source.json()["available"], source.text
    req = {"source_sha256": source.json()["source_sha256"], "price_arm": "Price", "sign_arm": "Sign", "combined_arm": "Both", "metric": "spend"}
    return eid, root, req


def test_new_experiment_retains_real_runner_outcomes_and_connects_review_to_csv(client, monkeypatch):
    eid, root, req = start_fixture(client, monkeypatch)
    folder = Path(".data") / PID / "marketing" / "experiments" / eid
    before = {p.name: p.read_bytes() for p in folder.iterdir()}
    response = client.post(root + "/preview", json=req)
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["complete_panel"] == 40 and [c["estimate"] for c in report["contrasts"]] == [5.5, 6.5, 7]
    exported = client.post(root + "/export.csv", json=req)
    assert exported.status_code == 200 and "attachment" in exported.headers["content-disposition"]
    rows = list(csv.reader(io.StringIO(exported.text)))
    assert ["metadata", "source_sha256", req["source_sha256"], "", ""] in rows
    assert ["persona_id", "complete", "00", "10", "01", "11"] in rows
    assert {p.name: p.read_bytes() for p in folder.iterdir()} == before


def test_raw_capture_precedes_intersection_and_missingness_suppresses_intervals(client, monkeypatch):
    eid, root, req = start_fixture(client, monkeypatch, missing_sign=True)
    report = client.post(root + "/preview", json=req).json()
    assert report["sampled_panel"] == 40 and report["complete_panel"] == 39
    assert [c["available"] for c in report["cells"]] == [40, 40, 39, 40]
    assert not report["intervals_available"] and all(c["ci_low"] is None for c in report["contrasts"])
    assert len([r for r in report["rows"] if not r["complete"]]) == 1
    original = client.get(f"/api/projects/{PID}/experiments/{eid}").json()["report"]
    assert original["panel_size"] == 39  # Existing headline still uses the common cohort.


def test_invalid_requests_stale_exports_and_legacy_sources_never_modify_the_experiment(client, monkeypatch):
    import json
    eid, root, req = start_fixture(client, monkeypatch)
    folder = Path(".data") / PID / "marketing" / "experiments" / eid
    path = folder / "paired-outcomes.json"; saved = path.read_bytes()
    for suffix in ["preview", "export.csv"]:
        for changes, status in [({"price_arm": "Absent"}, 400), ({"sign_arm": "Price"}, 422),
            ({"metric": ""}, 422), ({"metric": "net_profit"}, 422), ({"source_sha256": "0" * 64}, 409),
            ({"source_sha256": "bad"}, 422), ({"combined_arm": ""}, 422)]:
            response = client.post(root + "/" + suffix, json={**req, **changes})
            assert response.status_code == status, response.text
    assert path.read_bytes() == saved
    data = json.loads(saved); data["arms"][3]["outcomes"][0]["spend"] += 10
    path.write_text(json.dumps(data))
    assert client.post(root + "/export.csv", json=req).status_code == 409
    changed_source = client.get(root + "/source").json()
    assert changed_source["source_sha256"] != req["source_sha256"]
    path.unlink()
    source = client.get(root + "/source").json()
    assert not source["available"] and "Legacy" in source["reason"]
    assert client.post(root + "/preview", json=req).status_code == 409


def test_corrupt_partial_deleted_and_oversized_sources_fail_explicitly(client, monkeypatch):
    import json
    from store_emulator.application.storage.setups import metadata_path
    eid, root, req = start_fixture(client, monkeypatch)
    folder = Path(".data") / PID / "marketing" / "experiments" / eid
    path = folder / "paired-outcomes.json"; saved = path.read_bytes()
    data = json.loads(saved); data["experiment_id"] = "exp_other"
    inconsistent = json.loads(saved); inconsistent["arms"][0]["outcomes"][0]["bought"] = False
    for invalid in [b"{broken", b"x" * (8 * 1024 * 1024 + 1), json.dumps(data).encode(), json.dumps(inconsistent).encode()]:
        path.write_bytes(invalid)
        assert client.get(root + "/source").status_code == 409
        assert client.post(root + "/export.csv", json=req).status_code == 409
    path.write_bytes(saved)
    status_path = folder / "status.json"; status = json.loads(status_path.read_bytes())
    status["status"] = "running"; status_path.write_text(json.dumps(status))
    assert client.get(root + "/source").json()["available"] is False
    assert client.post(root + "/preview", json=req).status_code == 409
    status["job_id"] = "exp_other"; status_path.write_text(json.dumps(status))
    assert client.get(root + "/source").status_code == 409
    status_path.unlink()
    assert client.get(root + "/source").status_code == 404
    metadata_path(PID).unlink()
    assert client.post(root + "/preview", json=req).status_code == 404


def test_simultaneous_metric_reviews_are_independent_and_read_only(client, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    eid, root, req = start_fixture(client, monkeypatch)
    folder = Path(".data") / PID / "marketing" / "experiments" / eid
    before = {p.name: p.read_bytes() for p in folder.iterdir()}
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda metric: client.post(root + "/preview", json={**req, "metric": metric}), ["spend", "bought"]))
    assert all(r.status_code == 200 for r in responses)
    assert [r.json()["contrasts"][2]["estimate"] for r in responses] == [7, 0]
    assert {p.name: p.read_bytes() for p in folder.iterdir()} == before


def test_unsupported_raw_capture_does_not_turn_an_existing_ab_run_into_a_failure(client, monkeypatch):
    from store_emulator.application import marketing
    def invalid(*args, **kwargs):
        raise ValueError("Unsupported raw outcome")
    monkeypatch.setattr(marketing, "capture_paired_outcomes", invalid)
    # start_fixture expects retained outcomes, so exercise the start route with its own minimal fake runner.
    from store_emulator.domain.marketing import VariantResult
    async def run(evaluator, control, built, panel, skus, *, on_outcomes, **kwargs):
        on_outcomes([], [])
        return VariantResult(name="Control", customers=len(panel)), [VariantResult(name=built[0][0])], ""
    monkeypatch.setattr(marketing, "run_experiment", run)
    monkeypatch.setattr(marketing.executor, "submit", lambda fn: fn())
    response = client.post(f"/api/projects/{PID}/experiments", json={"setup_id": SETUP, "panel": 20,
        "variants": [{"name": "Price", "changes": [{"kind": "price", "sku": "A0001", "price": 149}]}]})
    assert response.status_code == 200 and response.json()["status"] == "completed"
    eid = response.json()["job_id"]
    source = client.get(f"/api/projects/{PID}/experiments/{eid}/factorial/source").json()
    assert not source["available"] and "not retained" in source["reason"]
