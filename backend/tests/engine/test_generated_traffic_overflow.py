"""Large model estimates still reach the population cap when visit data is supplied."""

import asyncio
import random
from collections import Counter

import pytest

from store_emulator.domain.store import DaySchedule
from store_emulator.engine.generators import persona as gen
from store_emulator.engine.generators.traffic_profile import TrafficProfile, reshape_hourly_counts


@pytest.mark.parametrize('exponent', [30, 100, 308, 400, 1000])
@pytest.mark.parametrize('scale_by_day', [False, True])
def test_large_counts_remain_nonnegative_exact_and_proportional(exponent, scale_by_day):
    count = 10 ** exponent
    profile = TrafficProfile(weights={day: {9: 1, 10: 3} for day in range(1, 8)})
    out = reshape_hourly_counts({8: 0, 9: count, 10: count, 11: 0}, profile, 1, scale_by_day=scale_by_day)
    assert out[8] == out[11] == 0
    assert all(isinstance(n, int) and n >= 0 for n in out.values())
    assert abs(out[10] - 3 * out[9]) <= 3
    if not scale_by_day: assert sum(out.values()) == 2 * count
    else: assert count < sum(out.values()) <= 3 * count


@pytest.mark.parametrize('exponent', [308, 400, 1000])
def test_full_customer_generation_with_observed_visit_times_reaches_the_existing_cap(exponent):
    class Model:
        async def generate_structured_async(self, schema, system, prompt, **kwargs):
            if schema is gen.TradeAreaProfile:
                return schema(keywords=['nearby'], identities=['resident'], purposes=['snack'])
            if schema is gen.DailyTrafficResult:
                return schema.model_validate_json('{"hourly_profiles":[{"hour":9,"visitor_count":' + str(10 ** exponent)
                    + ',"person_types":["resident"]}]}')
            return schema(personas=[gen.GeneratedPersona(identity='resident', age_group='20s', gender='Female',
                description='offline', intent='snack', purpose='snack').model_dump() for _ in range(prompt.count('\n['))])

    estimates = {}
    people = asyncio.run(gen.generate_batched(Model(), 'offline', '동네 주민',
        [DaySchedule(day=1, open_hour=9, close_hour=11)],
        pace=lambda p: gen.Pace(daily_cap=2, batch_size=2), estimates=estimates,
        traffic=TrafficProfile(weights={day: {9: 1, 10: 3} for day in range(1, 8)})))
    assert len(people) == len({p.id for p in people}) == estimates[1] == 1000
    assert Counter(p.arrival_hour for p in people) == {9: 250, 10: 750}
    assert sum(not p.twin_of for p in people) == 2


def test_ordinary_counts_keep_existing_rounding_and_tie_order():
    rng = random.Random(2610240904)
    for _ in range(250):
        counts = {h: rng.randrange(10000) for h in range(8, 18)}
        profile = TrafficProfile(weights={day: {h: rng.choice([.1, .5, 1., 3., 7.]) for h in counts} for day in range(1, 8)})
        hours = profile.weights[1]
        total = round(sum(counts.values()) * 7 * profile.weekday_shares()[1])
        weight = sum(hours.values())
        expected = {h: total * hours[h] / weight for h in counts}
        oracle = {h: int(x) for h, x in expected.items()}
        for h in sorted(counts, key=lambda h: -(expected[h] - int(expected[h])))[:total - sum(oracle.values())]:
            oracle[h] += 1
        assert reshape_hourly_counts(counts, profile, 1) == oracle
