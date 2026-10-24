"""Traffic estimates must describe the same hours and counts that customer generation consumes."""

import asyncio
import random
from collections import Counter

import pytest
from pydantic import ValidationError

from store_emulator.domain.store import DaySchedule
from store_emulator.engine.generators import persona as gen


class Model:
    def __init__(self, rows):
        self.rows = rows
        self.writes = 0

    async def generate_structured_async(self, schema, system, prompt, **kwargs):
        if schema is gen.TradeAreaProfile:
            return schema(keywords=["nearby"], identities=["shopper"], purposes=["snack"])
        if schema is gen.DailyTrafficResult:
            assert kwargs["max_retries"] == 3
            return schema.model_validate({"hourly_profiles": self.rows})
        assert issubclass(schema, gen.PersonaBatch)
        self.writes += 1
        return schema(personas=[gen.GeneratedPersona(identity="shopper", age_group="20s", gender="Female",
                      description="Offline boundary test", intent="snack", purpose="snack").model_dump() for _ in range(prompt.count("\n["))])


def row(hour, count):
    return {"hour": hour, "visitor_count": count, "person_types": ["shopper"]}


@pytest.mark.parametrize("rows", [
    [row(9, 10), row(9, 20)], [row(9, 20), row(9, 10)], [row(9, 10), row(9, 10)],
    [row(9, 0), row(9, 10)], [row(9, 20), row(10, -10)], [row(9, 10), row(10, -20)],
    [row(-1, 10)], [row(24, 10)], [row(True, 10)], [row(9, True)], [row(9.5, 10)], [row(9, 1.5)],
])
def test_invalid_estimate_cannot_be_used_as_a_population_or_money_scale(rows):
    model = Model(rows)
    estimates = {}
    with pytest.raises(ValidationError):
        asyncio.run(gen.generate_batched(model, "offline", "offline", [DaySchedule(day=1, open_hour=0, close_hour=24)],
                                        estimates=estimates))
    assert estimates == {} and model.writes == 0


@pytest.mark.parametrize("day,open_hour,close_hour", [(1, 0, 24), (7, 23, 24), (2, 0, 1), (6, 9, 18)])
@pytest.mark.parametrize("sample_cap", [1, 10, 1000])
def test_generated_valid_profiles_keep_estimates_population_and_clock_boundaries(day, open_hour, close_hour, sample_cap):
    rng = random.Random(day * 100 + sample_cap)
    rows = [row(hour, rng.randint(1, 20)) for hour in range(open_hour, close_hour)]
    rng.shuffle(rows)
    # Valid but closed hours are zeroed before either estimation or writing.
    rows += [row(hour, 50) for hour in range(24) if hour < open_hour or hour >= close_hour]
    model = Model(rows)
    estimates = {}
    people = asyncio.run(gen.generate_batched(model, "offline", "offline",
        [DaySchedule(day=day, open_hour=open_hour, close_hour=close_hour)], estimates=estimates,
        pace=lambda usual: gen.Pace(daily_cap=sample_cap, batch_size=usual.batch_size), seed=42))
    expected = {r["hour"]: r["visitor_count"] for r in rows if open_hour <= r["hour"] < close_hour}
    assert estimates == {day: sum(expected.values())}
    assert Counter(p.arrival_hour for p in people) == expected
    assert len({p.id for p in people}) == len(people) == estimates[day]
    assert all(int(p.day) == day for p in people)


def test_full_day_at_the_population_cap_preserves_all_hours():
    rows = [row(hour, 500) for hour in range(24)]
    model = Model(rows)
    estimates = {}
    people = asyncio.run(gen.generate_batched(model, "offline", "offline", [DaySchedule(day=1, open_hour=0, close_hour=24)],
        estimates=estimates, pace=lambda usual: gen.Pace(daily_cap=10, batch_size=usual.batch_size)))
    assert estimates == {1: 1000}
    assert len(people) == len({p.id for p in people}) == 1000
    assert set(p.arrival_hour for p in people) == set(range(24))
