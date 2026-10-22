"""A/B tests run on the shoppers who actually come, scale money by them, and do not pass off failed vision-model calls
as vision shoppers."""

import json
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from store_emulator.application import marketing
from store_emulator.application.simulation import RunOptions, run_shoppers
from store_emulator.domain.config import SimulationConfig
from store_emulator.domain.customer import CustomerResult
from store_emulator.domain.types import TokenUsage, Weekday
from store_emulator.engine.optimize.evaluate import LayoutEvaluator

PID = "proj_67916afd"
ROOT = f"/api/projects/{PID}/experiments"


@pytest.fixture
def app_client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TWINSTORE_LOCAL_VLM_AUTO", "0")
    monkeypatch.setattr(marketing, "executor", Mock(submit=lambda fn: fn()))
    from store_emulator.server.main import app
    with TestClient(app) as client:
        yield client


def _run(client: TestClient, body: dict[str, object]) -> dict[str, object]:
    response = client.post(ROOT, json=body)
    assert response.status_code == 200, response.text
    return client.get(f"{ROOT}/{response.json()['job_id']}").json()


@pytest.mark.parametrize("estimated", [None, 976])
def test_panel_and_daily_money_come_from_shoppers_who_arrive_while_open(app_client, monkeypatch, estimated):
    real_load = marketing._load_store   # pyright: ignore[reportPrivateUsage]

    def short_hours(pid: str, sid: str):
        store = real_load(pid, sid)
        for day in store.weekly_schedule:
            day.open_hour, day.close_hour = 12, 15
        return store

    monkeypatch.setattr(marketing, "_load_store", short_hours)
    if estimated is not None:   # the model estimated twice the visitors it wrote as customers
        meta = Path(".data") / PID / "metadata.json"
        data = json.loads(meta.read_text())
        meta.write_text(json.dumps({**data, "estimated_daily_visitors": {str(d): estimated for d in range(1, 6)}}))
    view = _run(app_client, {"setup_id": "setup_eaf5", "engine": "rule", "panel": 100, "seed": 3, "focus_skus": ["A0001"],
                             "variants": [{"name": "Disc", "changes": [{"kind": "discount", "sku": "A0001", "percent": -20}]}]})
    assert view["status"] == "completed", view["error"]
    report = view["report"]
    # Before, 57 of the 100 shoppers arrived while the store was closed and were dropped, blamed on failures.
    assert report["panel_size"] == 100
    assert not any("succeeded in every arm" in note for note in report["notes"])
    # Per-day money scales by the shoppers who come a day, as the run estimate counts them (not every persona).
    store = short_hours(PID, "setup_eaf5")
    shoppers = run_shoppers(PID, SimulationConfig(), store, marketing._personas(PID), RunOptions())[2]   # pyright: ignore[reportPrivateUsage]
    per_day = len(shoppers) / len({int(p.day) for p in shoppers})
    assert report["simulated_visitors_per_day"] == pytest.approx(per_day, abs=0.1)
    assert report["visitors_per_day"] == pytest.approx(per_day * (2 if estimated else 1), abs=0.2)
    # Every panel shopper has an outcome in every arm, so the 2×2 review can show intervals.
    snapshot = json.loads((Path(".data") / PID / "marketing" / "experiments" / view["job_id"] / "paired-outcomes.json").read_text())
    assert len(snapshot["panel_ids"]) == 100
    assert all({o["persona_id"] for o in arm["outcomes"]} == set(snapshot["panel_ids"]) for arm in snapshot["arms"])


def test_experiment_refuses_a_layout_nobody_visits_while_open(app_client, monkeypatch):
    real_load = marketing._load_store   # pyright: ignore[reportPrivateUsage]

    def closed(pid: str, sid: str):
        store = real_load(pid, sid)
        for day in store.weekly_schedule:
            day.open_hour, day.close_hour = 22, 23
        return store

    monkeypatch.setattr(marketing, "_load_store", closed)
    response = app_client.post(ROOT, json={"setup_id": "setup_eaf5", "panel": 50, "variants": [
        {"name": "Disc", "changes": [{"kind": "discount", "sku": "A0001", "percent": -20}]}]})
    assert response.status_code == 400 and "opening hours" in response.text


class _Failing:
    """A provider that answers nothing: every plan and shelf glance raises."""

    def __init__(self) -> None:
        self.calls = 0

    async def generate_structured_async(self, *args: object, **kwargs: object) -> object:
        self.calls += 1
        raise RuntimeError("503 provider overloaded")

    async def generate_structured_with_image_async(self, *args: object, **kwargs: object) -> object:
        self.calls += 1
        raise RuntimeError("503 provider overloaded")

    def get_usage(self) -> TokenUsage:
        return TokenUsage()

    def reset_usage(self) -> None:
        pass


def test_vision_test_whose_model_calls_all_fail_stops_instead_of_completing(app_client, monkeypatch):
    llm = _Failing()
    arms: list[int] = []
    evaluate = LayoutEvaluator.evaluate_customers

    async def counted(self, store, personas, **kwargs):
        arms.append(len(personas))
        return await evaluate(self, store, personas, **kwargs)

    monkeypatch.setattr(LayoutEvaluator, "evaluate_customers", counted)
    monkeypatch.setattr(marketing, "ensure_resolvable", lambda config: None)
    monkeypatch.setattr(marketing, "build_client", lambda *args, **kwargs: llm)
    view = _run(app_client, {"setup_id": "setup_eaf5", "engine": "vlm", "model": "openai/gpt-4o-mini", "panel": 20, "seed": 3,
                             "focus_skus": ["A0001"], "variants": [{"name": "Sign", "changes": [{"kind": "promo", "sku": "A0001", "promo": "SALE"}]}]})
    # Before, the test finished "completed" as "vision shoppers (openai/gpt-4o-mini)" with every call failed.
    assert view["status"] == "failed" and view["report"] is None
    assert "the vision model did not answer" in view["error"] and "503 provider overloaded" in view["error"]
    assert len(arms) == 1   # stopped after the control arm instead of paying for the variants


def _results(personas) -> list[CustomerResult]:
    return [CustomerResult(persona_id=p.id, day=Weekday.MON, arrival_time="12:00:00") for p in personas]


@pytest.mark.parametrize("variant_errors,fails", [(3, False), (45, True)])
def test_vision_test_reports_failed_calls_per_arm(app_client, monkeypatch, variant_errors, fails):
    metadata = iter([
        {"glances": 60, "errors": 5, "planning": {"plans": 20, "plan_errors": 2},
         "plan_records": [{"error": ""}, {"error": "RateLimitError: slow down"}]},
        {"glances": 60, "errors": variant_errors, "planning": {"plans": 20, "plan_errors": 0}, "plan_records": []},
    ])

    async def evaluate(self, store, personas, **kwargs):
        return _results(personas)

    monkeypatch.setattr(LayoutEvaluator, "evaluate_customers", evaluate)
    monkeypatch.setattr(LayoutEvaluator, "engine_metadata", lambda self: next(metadata))
    monkeypatch.setattr(marketing, "ensure_resolvable", lambda config: None)
    monkeypatch.setattr(marketing, "build_client", lambda *args, **kwargs: _Failing())
    view = _run(app_client, {"setup_id": "setup_eaf5", "engine": "vlm", "panel": 40, "seed": 3, "focus_skus": ["A0001"],
                             "variants": [{"name": "Sign", "changes": [{"kind": "promo", "sku": "A0001", "promo": "SALE"}]}]})
    if fails:
        assert view["status"] == "failed" and view["report"] is None
        assert view["error"].startswith("The vision model failed on 45 of 80 calls in Sign")
        return
    assert view["status"] == "completed", view["error"]
    note = next(n for n in view["report"]["notes"] if "vision-model calls failed" in n)
    assert "Control: 7 of 80" in note and "Sign: 3 of 80" in note and "paired differences" in note
