"""An empty regeneration must not report success and erase the previous population."""

from unittest.mock import Mock

import pytest

from store_emulator.application import generation_async as generation
from store_emulator.application.storage.generations import init_generation, read_status
from store_emulator.application.storage.io import write_json
from store_emulator.application.storage.setups import metadata_path, personas_path
from store_emulator.domain.config import SimulationConfig
from store_emulator.domain.store import DaySchedule
from tests.engine.test_persona_missing_days import Model

PID, SID = "proj_empty", "setup_offline"


@pytest.mark.parametrize("schedules", [None, [], [DaySchedule(day=1, is_open=False)],
    [DaySchedule(day=day, is_open=False, open_hour=0, close_hour=0) for day in range(1, 8)]])
def test_no_operating_days_fail_without_calling_a_model_or_replacing_customers(tmp_path, monkeypatch, schedules):
    monkeypatch.chdir(tmp_path)
    meta = {"estimated_daily_visitors": {"1": 75}, "customer_profile": "Existing"}
    if schedules is not None:
        meta["weekly_schedule"] = [s.model_dump(mode="json") for s in schedules]
    write_json(metadata_path(PID), meta)
    write_json(personas_path(PID), [{"id": "previous-customer"}])
    before = metadata_path(PID).read_bytes(), personas_path(PID).read_bytes()
    client = Mock(return_value=Model(failed_day=0))
    monkeypatch.setattr(generation, "assistive_client", client)
    gid = init_generation(PID, SID, "persona")
    generation._run_persona_background(SimulationConfig(), PID, SID, gid, "")
    status = read_status(PID, gid)
    assert status["status"] == "failed"
    assert "open" in status["error"].lower()
    client.assert_not_called()
    assert (metadata_path(PID).read_bytes(), personas_path(PID).read_bytes()) == before


@pytest.mark.parametrize("has_existing_customers", [False, True])
def test_empty_open_day_generation_preserves_existing_population_and_traffic_estimate(
    tmp_path, monkeypatch, has_existing_customers,
):
    monkeypatch.chdir(tmp_path)
    meta = {"weekly_schedule": [DaySchedule(day=2, open_hour=9, close_hour=10).model_dump(mode="json")],
            "estimated_daily_visitors": {"2": 77}, "traffic_profile": {
                "weights": {str(d): {"9": 1 if d == 1 else 0.00001} for d in range(1, 8)}}}
    write_json(metadata_path(PID), meta)
    write_json(personas_path(PID), [{"id": "previous-customer"}] if has_existing_customers else [])
    before = metadata_path(PID).read_bytes(), personas_path(PID).read_bytes()
    monkeypatch.setattr(generation, "assistive_client", lambda *a, **k: Model(failed_day=0))
    gid = init_generation(PID, SID, "persona")
    generation._run_persona_background(SimulationConfig(), PID, SID, gid, "")
    status = read_status(PID, gid)
    assert status["status"] == "failed"
    assert "no customers" in status["error"].lower()
    assert (metadata_path(PID).read_bytes(), personas_path(PID).read_bytes()) == before
