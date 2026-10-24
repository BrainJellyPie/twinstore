"""Identifiers assigned by the harness must not invalidate otherwise usable customers."""

import asyncio
from collections import Counter

import pytest

from store_emulator.domain.store import DaySchedule
from store_emulator.engine.generators import persona as gen


@pytest.mark.parametrize("model_id", [None, 1, True, [], {"id": 1}, "x" * 41, "고객" * 200, "same", "", "omitted"],
                         ids=["null", "number", "boolean", "list", "object", "long_ascii", "long_unicode", "repeated", "empty", "omitted"])
def test_unused_model_ids_cannot_fail_a_population_or_change_assigned_ids(model_id):
    class Model:
        async def generate_structured_async(self, schema, system, prompt, **kwargs):
            if schema is gen.TradeAreaProfile:
                return schema(keywords=["local"], identities=["resident"], purposes=["snack"])
            if schema is gen.DailyTrafficResult:
                return schema(hourly_profiles=[gen.HourlyProfile(hour=9, visitor_count=3, person_types=["resident"]),
                                               gen.HourlyProfile(hour=10, visitor_count=2, person_types=["resident"])])
            people = [{"identity": "resident", "age_group": "30s", "gender": "Female" if i % 2 == 0 else "Male",
                       "description": "Visits the local shop.", "intent": "Buy a snack", "purpose": "snack",
                       "preferred_categories": ["snacks"], "budget_max": 500}
                      for i in range(prompt.count("\n["))]
            if model_id != "omitted":
                for person in people: person["id"] = model_id
            return schema.model_validate({"personas": people})

    estimates = {}
    people = asyncio.run(gen.generate_batched(Model(), "offline", "동네 주민",
        [DaySchedule(day=day, open_hour=9, close_hour=11) for day in [1, 2, 7]],
        batch_size=2, seed=42, estimates=estimates))
    assert Counter(int(p.day) for p in people) == estimates == {1: 5, 2: 5, 7: 5}
    assert len({p.id for p in people}) == 15
    for day in [1, 2, 7]:
        visits = [p for p in people if int(p.day) == day]
        assert [p.id for p in visits] == [f"F{day}001", f"M{day}001", f"F{day}002", f"M{day}002", f"F{day}003"]
        assert Counter(p.arrival_hour for p in visits) == {9: 3, 10: 2}
        assert all(p.preferred_categories == ["snacks"] and p.budget_max == 500 and not p.twin_of for p in visits)


def test_generation_schema_does_not_ask_the_model_to_assign_ids():
    schema = gen.PersonaBatch.model_json_schema()
    assert "id" not in schema["$defs"]["GeneratedPersona"]["properties"]
    assert "- id:" not in gen.persona_prompt()
