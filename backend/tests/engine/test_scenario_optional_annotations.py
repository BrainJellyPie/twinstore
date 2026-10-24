"""Missing commentary must not discard a valid operational scenario."""

import asyncio
import copy
import json

import httpx
import pytest
from openai import AsyncOpenAI
from pydantic import ValidationError

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.types import Weekday
from store_emulator.engine import llm_client
from store_emulator.engine.scenario import apply_to_personas, apply_to_store, compile_scenario
from store_emulator.engine.scenario_writer import ScenarioDraft, describe_scenario
from tests.engine.test_scenario_target_matching import target_store
from tests.engine.test_shelf_panel_boundaries import person

GOOD = {"name": "Friday sale", "weather": "rain", "only_days": [5], "notes": "Fans nearby.",
        "events": [{"kind": "sports_match", "intensity": .8, "start_hour": 18, "end_hour": 22, "note": "Match."}],
        "promotions": [{"target": "Cola 500ml", "discount_pct": 50, "label": "SALE"}], "stockouts": ["Lager Beer 500ml"]}


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("missing", ["notes", "event_note", "label", "all"])
@pytest.mark.parametrize("value", [None, "omitted", "금요일 할인"])
def test_optional_annotations_do_not_lose_discounts_stockouts_or_weekdays(monkeypatch, tmp_path, mode, missing, value):
    payload = copy.deepcopy(GOOD)
    changed = []
    for field, container, key in (("notes", payload, "notes"), ("event_note", payload["events"][0], "note"),
                                  ("label", payload["promotions"][0], "label")):
        if missing in {field, "all"}:
            changed.append(field)
            if value == "omitted":
                del container[key]
            else:
                container[key] = value
    original, calls = llm_client.litellm.acompletion, []
    store = target_store()
    before = store.model_dump()

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop", "message": {
                "role": "assistant", "content": json.dumps(payload)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/scenario-annotations", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            result = await describe_scenario(client, "Rainy Friday, a match, half-price Cola and no lager", store)
            scenario = result.scenario
            for field, actual, original_text in (("notes", scenario.notes, "Fans nearby."),
                    ("event_note", scenario.events[0].note, "Match."), ("label", scenario.promotions[0].label, "SALE")):
                expected = ("" if value is None or value == "omitted" else value) if field in changed else original_text
                assert actual == expected
            edited, _ = apply_to_store(store, scenario)
            items = {item.sku: item for rack in edited.racks for slot in rack.slots for item in slot.items}
            assert "s-beer" not in items and items["s-cola"].price == 50
            assert all(item.price == 100 for sku, item in items.items() if sku != "s-cola")
            assert scenario.events[0].start_hour == 18 and scenario.events[0].end_hour == 22
            people = [person(str(day)).model_copy(update={"day": day}) for day in Weekday]
            selected = apply_to_personas(people, scenario, compile_scenario(scenario), seed=0, scale_traffic=False)
            assert [p.day for p in selected] == [Weekday.FRI] and store.model_dump() == before
            assert await describe_scenario(client, "Rainy Friday, a match, half-price Cola and no lager", store) == result
            assert len(calls) == 1 and client.get_usage().cached_requests == 1

    asyncio.run(exercise())


@pytest.mark.parametrize("field", ["notes", "event_note", "label"])
@pytest.mark.parametrize("value", [[], {}, 123, "x" * 401])
def test_non_null_wrong_annotation_values_remain_invalid(field, value):
    payload = copy.deepcopy(GOOD)
    if field == "notes":
        payload[field] = value
    elif field == "event_note":
        payload["events"][0]["note"] = value
    else:
        payload["promotions"][0]["label"] = value
    with pytest.raises(ValidationError):
        ScenarioDraft.model_validate(payload)


@pytest.mark.parametrize("field", ["only_days", "events", "promotions", "stockouts"])
def test_missing_operational_lists_are_not_inferred_from_null(field):
    with pytest.raises(ValidationError):
        ScenarioDraft.model_validate({**GOOD, field: None})
