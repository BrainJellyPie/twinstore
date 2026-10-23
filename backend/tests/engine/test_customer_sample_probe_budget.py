"""A measured probe stays within the sample/count and request plan the user accepts."""

import asyncio
from collections import Counter

import pytest

from store_emulator.domain.store import DaySchedule
from store_emulator.engine.generators import persona as gen


@pytest.mark.parametrize("hours", [1, 2, 14, 24])
@pytest.mark.parametrize("pace", [gen.Pace(1000, 5, 20), gen.Pace(1000, 10, 100), gen.Pace(1000, 10, 1)])
@pytest.mark.parametrize("choose", ["all", "sample"])
@pytest.mark.parametrize("short_probe", [False, True])
def test_written_customers_and_requests_match_the_selected_plan(hours, pace, choose, short_probe):
    class Model:
        requests = 0

        async def generate_structured_async(self, schema, system, prompt, **kwargs):
            if schema is gen.TradeAreaProfile:
                return schema(keywords=["nearby"], identities=["shopper"], purposes=["snack"])
            if schema is gen.DailyTrafficResult:
                return schema(hourly_profiles=[gen.HourlyProfile(hour=h, visitor_count=20, person_types=["shopper"])
                                               for h in range(hours)])
            self.requests += 1
            n = 1 if short_probe and self.requests == 1 else prompt.count("\n[")
            return gen.PersonaBatch(personas=[gen.GeneratedPersona(identity="shopper", age_group="20s", gender="Female",
                description=f"{self.requests}-{i}", intent="snack", purpose="snack") for i in range(n)])

    plans, progress = [], []

    async def decide(plan):
        plans.append(plan)
        return getattr(plan, choose).per_day

    model = Model()
    people = asyncio.run(gen.generate_batched(model, "offline", "offline",
        [DaySchedule(day=day, open_hour=0, close_hour=hours) for day in [1, 7]],
        pace=lambda usual: pace, decide=decide, on_progress=lambda done, total: progress.append((done, total))))
    plan = getattr(plans[0], choose)
    written = [p for p in people if not p.twin_of]
    assert len(written) == plan.customers
    assert model.requests == plan.requests
    assert Counter(p.day for p in written) == {day: min(plan.per_day, hours * 20) for day in [1, 7]}
    assert Counter((int(p.day), p.arrival_hour) for p in people) == {
        (day, hour): 20 for day in [1, 7] for hour in range(hours)}
    assert len({p.id for p in people}) == len(people)
    assert progress[-1] == (plan.customers, plan.customers)


def test_a_short_quiet_hour_probe_does_not_hide_the_remaining_request():
    class Model:
        requests = 0

        async def generate_structured_async(self, schema, system, prompt, **kwargs):
            if schema is gen.TradeAreaProfile:
                return schema(keywords=[], identities=["shopper"], purposes=["snack"])
            if schema is gen.DailyTrafficResult:
                return schema(hourly_profiles=[gen.HourlyProfile(hour=h, visitor_count=1, person_types=["shopper"])
                                               for h in range(10)])
            self.requests += 1
            return gen.PersonaBatch(personas=[gen.GeneratedPersona(identity="shopper", age_group="20s", gender="Female",
                description="offline", intent="snack", purpose="snack") for _ in range(prompt.count("\n["))])

    plans = []

    async def decide(plan):
        plans.append(plan)
        return plan.all.per_day

    model = Model()
    people = asyncio.run(gen.generate_batched(model, "offline", "offline",
        [DaySchedule(day=1, open_hour=0, close_hour=10)], decide=decide))
    assert len(people) == 10 and model.requests == 2
    assert plans[0].all.requests == 2 and plans[0].sample.requests == 2
