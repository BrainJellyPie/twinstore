"""A shelf-purchase predicate must not disappear when its shelf is missing."""

import asyncio
import json

import httpx
import pytest
from instructor.core.exceptions import InstructorRetryException
from openai import AsyncOpenAI
from pydantic import ValidationError

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.customer import TimelineEvent
from store_emulator.domain.rack import Rack, Slot, SlotItem
from store_emulator.domain.types import Action
from store_emulator.engine import llm_client
from store_emulator.engine.shopper_filter import find_shoppers
from tests.engine.test_shopper_filter_boundaries import STORE, customer


def sample():
    store = STORE.model_copy(update={"racks": [Rack(
        id="tea", type="shelf", shape=[[1]], position=(1, 1), rack_name="Tea shelf",
        slots=[Slot(block=0, face="E", items=[SlotItem(sku="green", name="Green Tea", price=100)])],
    )]})
    customers = {"away": customer("away")}
    for pid, action in [("browser", Action.BROWSE), ("buyer", Action.BUY)]:
        customers[pid] = customer(pid, spent=100 if action == Action.BUY else 0).model_copy(update={
            "timeline": [TimelineEvent(elapsed_sec=10, x=1, y=1, action=action,
                                       target_rack="tea", product_sku="green", price=100)],
        })
    return store, customers


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("there", ["yes", "no"])
@pytest.mark.parametrize("shelves", [None, [], ["  "], ["Unlisted shelf"]])
@pytest.mark.parametrize("recovery", ["corrected", "repeated", "legacy_cache"])
def test_shelf_condition_requires_a_resolvable_shelf_before_cache(
    monkeypatch, tmp_path, mode, there, shelves, recovery,
):
    store, customers = sample()
    before = [store.model_dump(), *(c.model_dump() for c in customers.values())]
    invalid = {"label": "Tea visitors", "bought_there": there}
    if shelves is not None:
        invalid["stopped_at"] = shelves
    valid = {**invalid, "stopped_at": ["Tea shelf"]}
    calls, retry_later = [], False
    original = llm_client.litellm.acompletion

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        answer = valid if retry_later or recovery == "legacy_cache" or recovery == "corrected" and len(calls) > 1 else invalid
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(answer)}}]})

    async def exercise():
        nonlocal retry_later
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/shopper-shelves", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, structured_sdk_retries=0, cache_dir=str(tmp_path)))
            generate, seeded = client.generate_structured_async, False

            async def generate_with_legacy_cache(schema, system, user, **kwargs):
                nonlocal seeded
                if recovery == "legacy_cache" and not seeded:
                    path = client._cache_path(schema, client._messages(system, user)[0], kwargs.get("seed"))
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(json.dumps({"result": invalid}))
                    seeded = True
                return await generate(schema, system, user, **kwargs)

            monkeypatch.setattr(client, "generate_structured_async", generate_with_legacy_cache)

            async def search():
                return await find_shoppers(client, "Find shoppers who visited the Tea shelf", customers, {}, store, "USD")

            if recovery == "repeated":
                with pytest.raises(InstructorRetryException):
                    await search()
                assert len(calls) == 2 and not list(tmp_path.rglob("*.json"))
                retry_later = True
            result = await search()
            assert result.persona_ids == (["buyer"] if there == "yes" else ["browser"])
            assert result.total == 3 and len(result.criteria) == 2 and not result.warnings
            assert await search() == result
            assert len(calls) == {"corrected": 2, "repeated": 3, "legacy_cache": 1}[recovery]
            assert client.get_usage().cached_requests == 1
            if recovery != "legacy_cache":
                feedback = json.dumps(calls[1]["messages"])
                assert "bought_there" in feedback and "stopped_at" in feedback
            assert all(json.loads(p.read_text())["result"]["stopped_at"] == ["Tea shelf"] for p in tmp_path.rglob("*.json"))
            assert [store.model_dump(), *(c.model_dump() for c in customers.values())] == before

    asyncio.run(exercise())


@pytest.mark.parametrize("there", ["yes", "no"])
@pytest.mark.parametrize("name", ["Tea shelf", " tea SHELF ", '"Tea shelf"', "the Tea shelf near the door"])
def test_existing_shelf_name_resolution_remains_usable(there, name):
    store, customers = sample()

    class Model:
        async def generate_structured_async(self, schema, *args, **kwargs):
            return schema.model_validate({"label": "Tea", "stopped_at": [name], "bought_there": there})

    result = asyncio.run(find_shoppers(Model(), "Find Tea visitors", customers, {}, store, "USD"))
    assert result.persona_ids == (["buyer"] if there == "yes" else ["browser"])


@pytest.mark.parametrize("shelves", [[], ["Tea shelf"], ["Unlisted shelf"]])
def test_unspecified_shelf_purchase_condition_keeps_existing_behavior(shelves):
    store, customers = sample()

    class Model:
        async def generate_structured_async(self, schema, *args, **kwargs):
            return schema.model_validate({"label": "Browse", "stopped_at": shelves})

    result = asyncio.run(find_shoppers(Model(), "Find visitors", customers, {}, store, "USD"))
    assert set(result.persona_ids) == ({"browser", "buyer"} if shelves == ["Tea shelf"] else set(customers))


@pytest.mark.parametrize("there", ["yes", "no"])
def test_one_unknown_alternative_keeps_the_known_shelf_and_warning(there):
    store, customers = sample()

    class Model:
        async def generate_structured_async(self, schema, *args, **kwargs):
            return schema.model_validate({"label": "Tea", "stopped_at": ["Moon shelf", "Tea shelf"], "bought_there": there})

    result = asyncio.run(find_shoppers(Model(), "Find Tea visitors", customers, {}, store, "USD"))
    assert result.persona_ids == (["buyer"] if there == "yes" else ["browser"])
    assert len(result.warnings) == 1 and "Moon shelf" in result.warnings[0]


def test_a_single_ambiguous_name_does_not_supply_a_shelf_target():
    store, customers = sample()
    store.racks.append(store.racks[0].model_copy(deep=True, update={
        "id": "snacks", "rack_name": "Snack shelf", "position": (3, 1),
    }))

    class Model:
        async def generate_structured_async(self, schema, *args, **kwargs):
            return schema.model_validate({"label": "Either", "stopped_at": ["Tea shelf or Snack shelf"], "bought_there": "no"})

    with pytest.raises(ValidationError, match="bought_there requires stopped_at"):
        asyncio.run(find_shoppers(Model(), "Find visitors", customers, {}, store, "USD"))


def test_duplicate_display_names_keep_all_rack_ids():
    store, customers = sample()
    store.racks.append(store.racks[0].model_copy(deep=True, update={"id": "tea2", "position": (3, 1)}))
    second = customers["browser"].model_copy(deep=True, update={"persona_id": "second"})
    second.timeline[0].target_rack = "tea2"
    customers["second"] = second

    class Model:
        async def generate_structured_async(self, schema, *args, **kwargs):
            return schema.model_validate({"label": "Tea", "stopped_at": ["Tea shelf"], "bought_there": "no"})

    result = asyncio.run(find_shoppers(Model(), "Find Tea visitors", customers, {}, store, "USD"))
    assert set(result.persona_ids) == {"browser", "second"} and not result.warnings
