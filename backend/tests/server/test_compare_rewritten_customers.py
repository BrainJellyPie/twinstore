"""Before 0.4.7 the customers could be written again after the layout of a final run was deleted; the new ones reuse
the ids (M1001, F1003, …). Comparing a run from before with one from after paired different people under one id."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

PID = "proj_e9427479"


def _person(pid: str, identity: str, age: str, gender: str, purpose: str, intent: str) -> dict[str, object]:
    """A customer as 0.4.5 kept it with its run (output/personas.json)."""
    return {"id": pid, "day": 1, "identity": identity, "age_group": age, "gender": gender, "description": f"{identity}.",
            "intent": intent, "purpose": purpose, "arrival_hour": 8, "preferred_categories": ["Coffee"], "budget_min": 500,
            "budget_max": 15000, "behavior_tendency": "Moves purposefully.", "basket_size": 0, "basket_kinds": 0,
            "category_rates": {}, "usual_products": [], "twin_of": ""}


def _visit(pid: str, spent: int) -> dict[str, object]:
    """A customer's visit as 0.4.5 wrote it (output/timeline.json), trimmed to entering and one purchase."""
    return {"persona_id": pid, "day": 1, "arrival_time": "08:00:58", "leave_time": "08:02:09", "timeline": [
        {"elapsed_sec": 0, "x": 0, "y": 9, "action": "enter", "duration": 0, "target_rack": "", "face": None,
         "description": "", "product_sku": "", "product_name": "", "price": 0, "quantity": 1, "origin": ""},
        {"elapsed_sec": 22, "x": 10, "y": 3, "action": "buy", "duration": 3, "target_rack": "r_014", "face": "W",
         "description": "picks a drink", "product_sku": "g_bde8bab26bee91aeb4d5e4ab07819fb1", "product_name": "Drink",
         "price": spent, "quantity": 1, "origin": "planned"}],
        "total_spent": spent, "engine_type": "rule_based", "dropped_invalid_buys": 0, "dropped_over_budget": 0}


EXECUTIVE = _person("M1001", "Corporate executives", "50s", "Male", "Monday morning breakfast", "Wants a black coffee.")
STUDENT = _person("M1001", "University students", "20s", "Male", "Late lunch", "Wants instant noodles.")
NURSE = _person("F1003", "Night-shift nurses", "30s", "Female", "After a night shift", "Wants a hangover drink.")


def _run(data: Path, run_id: str, people: list[dict[str, object]], spend: dict[str, int]) -> None:
    base = data / PID / "runs" / run_id
    (base / "output").mkdir(parents=True)
    (base / "status.json").write_text(json.dumps({
        "status": "completed", "error": "", "setup_id": "setup_787f13b0cf46403dbbf696f52bd4ce28", "preview": False,
        "created_at": "2026-10-22T16:37:00+00:00", "total_customers": len(people), "completed_customers": len(people),
        "failed_customers": 0, "engine_type": "rule_based", "seed": 1, "replicate": 0, "scenario": ""}))
    (base / "output" / "timeline.json").write_text(json.dumps([_visit(p, s) for p, s in spend.items()]))
    (base / "output" / "personas.json").write_text(json.dumps({str(p["id"]): p for p in people}))
    (base / "output" / "summary.json").write_text(json.dumps({"store_id": f"store_{PID}", "currency": "KRW"}))
    (base / "output" / "manifest.json").write_text(json.dumps({
        "engine_type": "rule_based", "model": "", "seed": 1, "replicate": 0, "exposure_model": "visibility",
        "route_ordering": "planned", "package_version": "0.2.0", "scenario": "", "scenario_id": "", "town": ""}))


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TWINSTORE_LOCAL_VLM", "0")
    data = tmp_path / ".data"
    (data / PID).mkdir(parents=True)
    (data / PID / "metadata.json").write_text(json.dumps({"project_id": PID, "name": "Old store", "currency": "KRW"}))
    from store_emulator.server import main
    monkeypatch.setattr(main, "seed_sample_projects", lambda: 0)
    with TestClient(main.app) as test_client:
        yield test_client, data


def test_customers_written_again_under_the_same_ids_are_not_paired(client):
    test_client, data = client
    _run(data, "run_1a669b", [EXECUTIVE, NURSE], {"M1001": 1500, "F1003": 5400})
    _run(data, "run_9e577f", [STUDENT, NURSE], {"M1001": 900, "F1003": 6400})
    report = test_client.get(f"/api/projects/{PID}/compare", params={"a": "run_1a669b", "b": "run_9e577f"}).json()
    assert report["paired_customers"] == 1 and report["unpaired_a"] == 1 and report["unpaired_b"] == 1
    spend = next(m for m in report["metrics"] if m["metric"] == "spend")
    assert (spend["mean_a"], spend["mean_b"]) == (5400, 6400)          # the nurse alone, not 3450 vs 3650
    assert "1 customers have the same id in both runs but are different people" in report["notes"][0]


def test_the_same_customers_stay_paired(client):
    test_client, data = client
    rich = {**EXECUTIVE, "budget_max": 30000}                          # a situation's budgets leave the person as is
    _run(data, "run_1a669b", [EXECUTIVE, NURSE], {"M1001": 1500, "F1003": 5400})
    _run(data, "run_9e577f", [rich, NURSE], {"M1001": 900, "F1003": 6400})
    report = test_client.get(f"/api/projects/{PID}/compare", params={"a": "run_1a669b", "b": "run_9e577f"}).json()
    assert report["paired_customers"] == 2 and report["unpaired_a"] == 0
    assert not any("different people" in note for note in report["notes"])
