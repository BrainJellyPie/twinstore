"""An unresolvable generated product predicate must not silently disappear."""

import asyncio
import json

import httpx
import pytest
from instructor.core.exceptions import InstructorRetryException
from openai import AsyncOpenAI
from pydantic import ValidationError

from store_emulator.domain.config import LLMConfig
from store_emulator.engine import llm_client
from store_emulator.engine.shopper_filter import find_shoppers
from tests.engine.test_shopper_filter_boundaries import customer
from tests.engine.test_shopper_shelf_dependencies import sample


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("field", ["bought_products", "skipped_products"])
@pytest.mark.parametrize("names", [["Moonberry Soda"], ["  "]])
@pytest.mark.parametrize("recovery", ["corrected", "repeated", "legacy_cache"])
def test_unresolvable_product_predicates_are_corrected_before_matching_or_caching(
    monkeypatch, tmp_path, mode, field, names, recovery,
):
    store, customers = sample()
    before = [store.model_dump(), *(c.model_dump() for c in customers.values())]
    invalid = {"label": "Product shoppers", field: names}
    valid = {"label": "Product shoppers", field: ["Green Tea"]}
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
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/shopper-products", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, structured_sdk_retries=0, cache_dir=str(tmp_path)))
            generate, seeded = client.generate_structured_async, False

            async def cached(schema, system, user, **kwargs):
                nonlocal seeded
                if recovery == "legacy_cache" and not seeded:
                    path = client._cache_path(schema, client._messages(system, user)[0], kwargs.get("seed"))
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(json.dumps({"result": invalid}))
                    seeded = True
                return await generate(schema, system, user, **kwargs)

            monkeypatch.setattr(client, "generate_structured_async", cached)

            async def search():
                return await find_shoppers(client, "Find Green Tea shoppers", customers, {}, store, "USD")

            if recovery == "repeated":
                with pytest.raises(InstructorRetryException):
                    await search()
                assert len(calls) == 2 and not list(tmp_path.rglob("*.json"))
                retry_later = True
            result = await search()
            assert set(result.persona_ids) == ({"buyer"} if field == "bought_products" else {"browser", "away"})
            assert len(result.criteria) == 1 and not result.warnings
            assert await search() == result
            assert len(calls) == {"corrected": 2, "repeated": 3, "legacy_cache": 1}[recovery]
            assert client.get_usage().cached_requests == 1
            if recovery != "legacy_cache":
                feedback = json.dumps(calls[1]["messages"])
                assert field in feedback and "listed product" in feedback
            assert all(json.loads(p.read_text())["result"][field] == ["Green Tea"] for p in tmp_path.rglob("*.json"))
            assert [store.model_dump(), *(c.model_dump() for c in customers.values())] == before

    asyncio.run(exercise())


@pytest.mark.parametrize("field", ["bought_products", "skipped_products"])
@pytest.mark.parametrize("names", [[], [" green TEA "], ['"Green Tea"'], ["the Green Tea near the door"], ["Missing", "Green Tea"]])
def test_existing_known_names_empty_lists_and_partly_known_conditions_keep_their_meaning(field, names):
    store, customers = sample()

    class Model:
        async def generate_structured_async(self, schema, *args, **kwargs):
            return schema.model_validate({"label": "Tea", field: names})

    result = asyncio.run(find_shoppers(Model(), "Find Tea shoppers", customers, {}, store, "USD"))
    assert set(result.persona_ids) == (set(customers) if not names else {"buyer"} if field == "bought_products" else {"browser", "away"})
    assert bool(result.warnings) == ("Missing" in names)


@pytest.mark.parametrize("field", ["bought_products", "skipped_products"])
@pytest.mark.parametrize("empty_store", [False, True])
def test_empty_or_ambiguous_catalog_cannot_supply_a_product_target(field, empty_store):
    store, customers = sample()
    if empty_store:
        store.racks = []
    else:
        items = store.racks[0].slots[0].items
        items.append(items[0].model_copy(update={"sku": "black", "name": "Black Tea"}))

    class Model:
        async def generate_structured_async(self, schema, *args, **kwargs):
            return schema.model_validate({"label": "Tea", field: ["Green Tea and Black Tea"]})

    with pytest.raises(ValidationError, match=field):
        asyncio.run(find_shoppers(Model(), "Find Tea shoppers", customers, {}, store, "USD"))


@pytest.mark.parametrize("field", ["bought_products", "skipped_products"])
@pytest.mark.parametrize("same_name", [False, True])
def test_product_name_groups_retain_all_skus_and_same_sku_aliases(field, same_name):
    store, customers = sample()
    item = store.racks[0].slots[0].items[0]
    extra_sku = "other-green" if same_name else item.sku
    store.racks[0].slots[0].items.append(item.model_copy(update={
        "sku": extra_sku, "name": item.name if same_name else "Black Tea",
    }))
    customers["other"] = customer("other", spent=100).model_copy(update={
        "timeline": [customers["buyer"].timeline[0].model_copy(update={"product_sku": extra_sku})],
    })

    class Model:
        async def generate_structured_async(self, schema, *args, **kwargs):
            return schema.model_validate({"label": "Tea", field: ["Green Tea" if same_name else "Green Tea and Black Tea"]})

    result = asyncio.run(find_shoppers(Model(), "Find Tea shoppers", customers, {}, store, "USD"))
    assert set(result.persona_ids) == ({"buyer", "other"} if field == "bought_products" else {"away", "browser"})
    assert not result.warnings
