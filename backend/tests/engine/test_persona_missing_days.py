"""A failed or empty weekday must not silently become a successful partial population."""

import asyncio
from collections import Counter

import pytest
from pydantic import ValidationError

from store_emulator.domain.store import DaySchedule
from store_emulator.domain.types import TokenUsage, WEEKDAY_LABELS
from store_emulator.engine.generators import persona as gen
from store_emulator.engine.generators.traffic_profile import TrafficProfile


class Model:
    max_parallel = None

    def __init__(self, failed_day=2, failure="empty", first_only=False, short=False):
        self.failed_day, self.failure, self.first_only, self.short = failed_day, failure, first_only, short
        self.calls = Counter()

    def get_usage(self):
        return TokenUsage()

    async def generate_structured_async(self, schema, system, prompt, **kwargs):
        assert kwargs["max_retries"] == 3
        if schema is gen.TradeAreaProfile:
            return schema(keywords=["nearby"], identities=["shopper"], purposes=["snack"])
        if schema is gen.DailyTrafficResult:
            return schema(hourly_profiles=[gen.HourlyProfile(hour=9, visitor_count=20, person_types=["shopper"])])
        assert schema is gen.PersonaBatch
        day = next(int(d) for d, label in WEEKDAY_LABELS.items() if f"요일: {label}\n" in prompt)
        self.calls[day] += 1
        if day == self.failed_day and (not self.first_only or self.calls[day] == 1):
            if self.failure == "provider":
                raise RuntimeError("offline provider failure")
            return schema.model_validate({"personas": []})
        n = 1 if self.short else prompt.count("\n[")
        return schema(personas=[gen.GeneratedPersona(identity="shopper", age_group="20s", gender="Female",
                      description="Offline test", intent="snack", purpose="snack") for _ in range(n)])


def schedules():
    return [DaySchedule(day=d, open_hour=9, close_hour=10) for d in [1, 2, 7]]


def test_empty_batch_is_invalid_for_structured_response_retry():
    with pytest.raises(ValidationError):
        gen.PersonaBatch.model_validate({"personas": []})


@pytest.mark.parametrize("failed_day", [1, 2, 7])
@pytest.mark.parametrize("failure", ["empty", "provider"])
@pytest.mark.parametrize("cap", [1, 20])
def test_losing_a_whole_day_cannot_return_a_partial_week(failed_day, failure, cap):
    with pytest.raises(ValueError, match="No customers were generated for"):
        asyncio.run(gen.generate_batched(Model(failed_day, failure), "offline", "offline", schedules(),
                    pace=lambda usual: gen.Pace(daily_cap=cap, batch_size=usual.batch_size)))


@pytest.mark.parametrize("failure", ["empty", "provider"])
def test_failed_probe_stops_before_requesting_a_write_choice(failure):
    decisions = []

    async def decide(plan):
        decisions.append(plan)
        return 20

    with pytest.raises(gen.TooManyBatchesFailed):
        asyncio.run(gen.generate_batched(Model(1, failure), "offline", "offline", schedules(), decide=decide))
    assert decisions == []


@pytest.mark.parametrize("failure", ["empty", "provider"])
def test_one_bad_batch_can_use_the_same_days_surviving_customers(failure):
    estimates = {}
    people = asyncio.run(gen.generate_batched(Model(2, failure, first_only=True), "offline", "offline", schedules(),
                                              estimates=estimates))
    assert estimates == {1: 20, 2: 20, 7: 20}
    assert Counter(int(p.day) for p in people) == estimates
    assert sum(bool(p.twin_of) for p in people if int(p.day) == 2) == 10
    assert len({p.id for p in people}) == 60


def test_short_nonempty_batches_still_fill_every_days_population():
    people = asyncio.run(gen.generate_batched(Model(failed_day=0, short=True), "offline", "offline", schedules()))
    assert Counter(int(p.day) for p in people) == {1: 20, 2: 20, 7: 20}
    assert len({p.id for p in people}) == 60


def test_zero_traffic_and_closed_days_do_not_require_customers():
    traffic = TrafficProfile(weights={d: {9: 1 if d == 1 else 0.00001} for d in range(1, 8)})
    hours = schedules() + [DaySchedule(day=4, is_open=False)]
    people = asyncio.run(gen.generate_batched(Model(failed_day=0), "offline", "offline", hours, traffic=traffic))
    assert Counter(int(p.day) for p in people) == {1: 140}


@pytest.mark.parametrize("failure", ["empty", "provider"])
def test_failed_background_generation_preserves_saved_customers_and_estimates(tmp_path, monkeypatch, failure):
    from store_emulator.application import generation_async as ga
    from store_emulator.application.storage.generations import init_generation, read_status
    from store_emulator.application.storage.io import read_json, write_json
    from store_emulator.application.storage.setups import metadata_path, personas_path
    from store_emulator.domain.config import SimulationConfig

    monkeypatch.chdir(tmp_path)
    pid, sid = "proj_missing_day", "setup_offline"
    metadata = {"weekly_schedule": [s.model_dump(mode="json") for s in schedules()],
                "estimated_daily_visitors": {"1": 31, "2": 32, "7": 37}}
    saved_people = [{"id": "previous-population"}]
    write_json(metadata_path(pid), metadata)
    write_json(personas_path(pid), saved_people)
    gid = init_generation(pid, sid, "persona")
    monkeypatch.setattr(ga, "assistive_client", lambda *args, **kwargs: Model(2, failure))

    async def decide(*args):
        return 1000

    monkeypatch.setattr(ga, "_decide", decide)
    ga._run_persona_background(SimulationConfig(), pid, sid, gid, "")
    status = read_status(pid, gid)
    assert status["status"] == "failed"
    assert "TUE" in status["error"]
    assert read_json(personas_path(pid)) == saved_people
    assert read_json(metadata_path(pid)) == metadata
