"""A weekly schedule must describe each weekday once across generation and admission."""

import asyncio
from collections import Counter

import pytest
from pydantic import ValidationError

from store_emulator.domain.store import DaySchedule, Store
from store_emulator.engine.generators import persona as gen
from tests.engine.test_persona_missing_days import Model


def duplicate_rows(day, kind):
    first = {"day": day, "open_hour": 9, "close_hour": 10}
    second = {**first, "day": str(day)}
    if kind == "split":
        second.update(open_hour=17, close_hour=18)
    if kind == "closed":
        second["is_open"] = False
    return [first, second]


@pytest.mark.parametrize("day", range(1, 8))
@pytest.mark.parametrize("kind", ["same", "split", "closed"])
def test_store_rejects_repeated_weekdays_including_conflicting_windows(day, kind):
    with pytest.raises(ValidationError, match="at most once"):
        Store(id="s", name="s", type="s", grid_size=(8, 8), weekly_schedule=duplicate_rows(day, kind))


@pytest.mark.parametrize("kind", ["same", "split", "closed"])
def test_generation_rejects_old_duplicate_metadata_before_any_model_calls(kind):
    class UnusedModel:
        async def generate_structured_async(self, *args, **kwargs):
            pytest.fail("Invalid weekly schedules must be rejected before model calls")

    hours = [DaySchedule.model_validate(row) for row in duplicate_rows(7, kind)]
    with pytest.raises(ValueError, match="at most once"):
        asyncio.run(gen.generate_batched(UnusedModel(), "offline", "offline", hours))


@pytest.mark.parametrize("days", [[], [1], [7, 1, 4], [7, 6, 5, 4, 3, 2, 1]])
def test_empty_partial_and_reordered_unique_schedules_remain_valid(days):
    rows = [DaySchedule(day=d, open_hour=23, close_hour=24, is_open=d != 4) for d in days]
    store = Store(id="s", name="s", type="s", grid_size=(8, 8), weekly_schedule=rows)
    assert [int(row.day) for row in store.weekly_schedule] == days


def test_reordered_week_generation_has_unique_ids_and_matching_estimates():
    rows = [DaySchedule(day=d, open_hour=9, close_hour=10) for d in [7, 3, 1, 6, 2, 5, 4]]
    estimates = {}
    people = asyncio.run(gen.generate_batched(Model(failed_day=0), "offline", "offline", rows, estimates=estimates))
    assert Counter(int(p.day) for p in people) == estimates == {d: 20 for d in range(1, 8)}
    assert len(people) == len({p.id for p in people}) == 140


def test_oversized_repeated_schedule_is_rejected():
    from store_emulator.domain.store import validate_weekly_schedule

    with pytest.raises(ValueError, match="at most once"):
        validate_weekly_schedule([DaySchedule(day=1)] * 100000)
