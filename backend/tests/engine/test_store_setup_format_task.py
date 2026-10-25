"""Separate the layout choice from the tiny model's optional form fields."""

import asyncio

import pytest
from instructor.core.exceptions import FailedAttempt, IncompleteOutputException, InstructorRetryException

from store_emulator.engine.generators.store_setup_writer import draft_store_setup


@pytest.mark.parametrize("previous", ["", "urban", "Missing"])
@pytest.mark.parametrize("supplied", [False, True])
def test_format_task_preserves_supplied_and_unspecified_facts(previous, supplied):
    facts = {"name": "동네 약국", "description": "의약품과 생활용품", "format": previous,
             "address": "서울" if supplied else "", "open_days": "weekend" if supplied else None,
             "open_hour": 10 if supplied else None, "close_hour": 18 if supplied else None,
             "currency": "KRW" if supplied else None, "rationale": "Owner details"}
    calls = []

    class Model:
        async def generate_structured_async(self, schema, system, user, **kwargs):
            calls.append((schema, system, user, kwargs))
            if len(calls) == 1:
                return schema.model_validate(facts)
            if "store_type" in schema.model_fields:
                return schema.model_validate({"store_type": "pharmacy"})
            wire = schema.model_json_schema()
            assert set(wire["properties"]) == {"format"}
            assert wire["required"] == ["format"]
            assert wire["properties"]["format"]["enum"] == ["urban", "drugstore"]
            assert "drugstore: Pharmacy (pharmacy)" in user
            assert "Long template description" not in user
            assert kwargs == {"max_retries": 2, "seed": 0, "max_tokens": 160}
            # Extra fields from an unconstrained provider cannot overwrite facts.
            return schema.model_validate({"format": "drugstore", "open_days": "7", "currency": "USD"})

    result = asyncio.run(draft_store_setup(Model(), "A pharmacy selling household goods",
        [("urban", "Convenience store", "convenience", "Long template description"),
         ("drugstore", "Pharmacy", "pharmacy", "Long template description")]))
    assert len(calls) == 3
    assert (result.template_id, result.store_type) == ("drugstore", "pharmacy")
    assert all(getattr(result, key) == value for key, value in facts.items() if key != "format")
    assert not result.warnings


@pytest.mark.parametrize("kind", ["direct", "wrapped", "ordinary", "always"])
def test_format_cutoff_has_one_bounded_expansion(kind):
    cutoff = IncompleteOutputException("cut off")
    error = InstructorRetryException("failed", n_attempts=1, total_usage=0,
        failed_attempts=[FailedAttempt(1, cutoff)]) if kind == "wrapped" else (
        ValueError("max_tokens length limit") if kind == "ordinary" else cutoff)
    calls = []

    class Model:
        async def generate_structured_async(self, schema, *args, **kwargs):
            calls.append((args, kwargs))
            if len(calls) == 1:
                return schema.model_validate({"name": "Shop", "open_days": "weekend", "currency": "KRW"})
            if len(calls) == 2 or kind == "always":
                raise error
            return schema.model_validate({"format": "corner"})

    pending = draft_store_setup(Model(), "Corner shop", [("corner", "Corner", "convenience", "Local shop")])
    if kind in {"ordinary", "always"}:
        with pytest.raises(type(error)):
            asyncio.run(pending)
    else:
        result = asyncio.run(pending)
        assert (result.name, result.template_id, result.open_days, result.currency) == ("Shop", "corner", "weekend", "KRW")
    assert [kw["max_tokens"] for _, kw in calls] == ([900, 160] if kind == "ordinary" else [900, 160, 320])
    if len(calls) == 3:
        assert calls[1][0] == calls[2][0]
