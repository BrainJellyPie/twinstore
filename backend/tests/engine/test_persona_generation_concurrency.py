"""All weekdays share the requested customer-writing concurrency budget."""

import asyncio

import pytest

from store_emulator.domain.store import DaySchedule
from store_emulator.engine.generators import persona as gen


class Model:
    def __init__(self, capacity=None):
        self.capacity = capacity
        self.active = self.peak = self.rejected = 0

    async def generate_structured_async(self, schema, system, prompt, **kwargs):
        if schema is gen.TradeAreaProfile:
            return schema(keywords=[], identities=["shopper"], purposes=["snack"])
        if issubclass(schema, gen.DailyTrafficResult):
            return schema(hourly_profiles=[gen.HourlyProfile(hour=12, visitor_count=60, person_types=["shopper"])])
        self.active += 1
        self.peak = max(self.peak, self.active)
        try:
            if self.capacity is not None and self.active > self.capacity:
                self.rejected += 1
                raise RuntimeError("offline provider concurrency limit")
            await asyncio.sleep(0)  # Let the other weekday batches contend for the shared semaphore.
            return gen.PersonaBatch(personas=[gen.GeneratedPersona(identity="shopper", age_group="20s", gender="Female",
                description="offline", intent="snack", purpose="snack") for _ in range(prompt.count("\n["))])
        finally:
            self.active -= 1


def generate(model, days, **kwargs):
    return asyncio.run(gen.generate_batched(model, "offline", "offline",
        [DaySchedule(day=day, open_hour=0, close_hour=24) for day in range(1, days + 1)],
        pace=lambda usual: gen.Pace(1000, 3, 20), **kwargs))


@pytest.mark.parametrize("days", [1, 2, 7])
@pytest.mark.parametrize("limit", [1, 2, 10, 20, 25])
def test_weekdays_respect_one_shared_requested_limit(days, limit):
    model = Model()
    people = generate(model, days, max_concurrent=limit)
    assert model.peak == min(limit, days * 20)
    assert len(people) == days * 60
    assert not any(p.twin_of for p in people)


def test_default_generation_keeps_the_default_ten_request_limit():
    model = Model()
    generate(model, 7)
    assert model.peak == 10


def test_provider_at_configured_capacity_does_not_reject_weekday_batches():
    model = Model(capacity=10)
    people = generate(model, 7, max_concurrent=10)
    assert model.rejected == 0
    assert len(people) == 420
    assert not any(p.twin_of for p in people)
