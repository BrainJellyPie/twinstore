"""Daily money must use the traffic scale of the weekdays actually analyzed."""

import pytest

from store_emulator.application import generation_async as generation, marketing
from store_emulator.application.storage.io import read_json, write_json
from store_emulator.application.storage.setups import metadata_path, personas_path, read_setup, setup_path
from store_emulator.domain.persona import Persona
from tests.server.test_experiment_start_snapshot import study
from tests.server.test_simulation_setup_races import PID, SID, layout


def _people(counts):
    return [Persona(id=f"{day}_{n}", day=day, identity="shopper", age_group="20s", gender="Female",
                    description="offline", intent="snack", purpose="snack")
            for day, count in counts.items() for n in range(count)]


@pytest.mark.parametrize("day", range(1, 8))
@pytest.mark.parametrize("own_scale", [1, 2, 10])
@pytest.mark.parametrize("other_scale", [1, 5, 100])
def test_excluded_weekdays_cannot_change_the_selected_days_money(tmp_path, monkeypatch, day, own_scale, other_scale):
    monkeypatch.chdir(tmp_path)
    counts = {weekday: 7 + weekday for weekday in range(1, 8)}
    everyone = _people(counts)
    write_json(metadata_path(PID), {"estimated_daily_visitors": {
        str(d): n * (own_scale if d == day else other_scale) for d, n in counts.items()}})
    coming = [p for p in everyone if p.day == day]
    assert generation.visitors_per_day_coming(PID, everyone, coming) == (counts[day] * own_scale, counts[day])


@pytest.mark.parametrize("multiplier", [1, 3])
def test_each_partial_day_uses_its_own_sample_ratio_without_intermediate_rounding(tmp_path, monkeypatch, multiplier):
    monkeypatch.chdir(tmp_path)
    everyone = _people({1: 9, 2: 3, 7: 11})
    coming = [p for p in everyone if p.id in {"1_0", "1_1", "2_0"}] * multiplier
    write_json(metadata_path(PID), {"estimated_daily_visitors": {"1": 90, "2": 6, "7": 1100}})
    assert generation.visitors_per_day_coming(PID, everyone, coming) == (11 * multiplier, 1.5 * multiplier)


@pytest.mark.parametrize("bad", [None, False, "100", -1, float("nan"), float("inf"), float("-inf"), 10**400])
def test_invalid_or_missing_day_estimate_falls_back_without_poisoning_valid_days(tmp_path, monkeypatch, bad):
    monkeypatch.chdir(tmp_path)
    everyone = _people({1: 10, 2: 5})
    write_json(metadata_path(PID), {"estimated_daily_visitors": {"1": bad, "2": 50}})
    assert generation.visitors_per_day(PID, everyone) == (30, 7.5)
    assert generation.visitors_per_day_coming(PID, everyone, everyone) == (30, 7.5)


@pytest.mark.parametrize("metadata", [None, False, [], "metadata", {}, {"estimated_daily_visitors": []}])
def test_legacy_or_malformed_metadata_preserves_observed_counts(tmp_path, monkeypatch, metadata):
    monkeypatch.chdir(tmp_path)
    everyone = _people({1: 9, 7: 4})
    write_json(metadata_path(PID), metadata)
    assert generation.visitors_per_day(PID, everyone) == (6.5, 6.5)
    assert generation.visitors_per_day_coming(PID, everyone, everyone[-4:]) == (4, 4)
    assert generation.visitors_per_day_coming(PID, everyone, []) == (0, 0)
    assert generation.visitors_per_day_coming(PID, [], everyone[-4:]) == (4, 4)


def test_daily_scaling_reaches_the_completed_experiment_report(study):
    client, submit, _, body = study
    everyone = _people({1: 100, 2: 20})
    write_json(personas_path(PID), [p.model_dump(mode="json") for p in everyone])
    meta = read_json(metadata_path(PID))
    write_json(metadata_path(PID), {**meta, "estimated_daily_visitors": {"1": 10000, "2": 40}})
    setup = read_setup(PID, SID)
    setup["store"]["weekly_schedule"] = [{"day": 2, "open_hour": 9, "close_hour": 18, "is_open": True}]
    write_json(setup_path(PID, SID), setup)
    started = client.post(f"/api/projects/{PID}/experiments", json=body)
    assert started.status_code == 200, started.text
    submit.call_args.args[0]()
    view = marketing.get_experiment(PID, started.json()["job_id"])
    assert view.status == "completed", view.error
    assert view.report.simulated_visitors_per_day == 20
    assert view.report.visitors_per_day == 40
