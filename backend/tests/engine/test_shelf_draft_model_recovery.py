"""A nonexistent shelf-test product must be corrected before a draft is cached."""

import asyncio
import json

import httpx
import pytest
from instructor.core.exceptions import InstructorRetryException
from openai import AsyncOpenAI

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.rack import SlotItem
from store_emulator.engine import llm_client
from store_emulator.engine.marketing.shelf_test_design import _Draft, design_shelf_test, to_design
from tests.engine.test_shelf_design_boundaries import store


@pytest.mark.parametrize("product", ["", "   ", "Steak", "Imaginary soda", "Water", "없는 상품", "W" * 160])
@pytest.mark.parametrize("recovers", [False, True])
def test_invalid_target_gets_one_correction_and_never_poisoned_cache(monkeypatch, tmp_path, product, recovers):
    original = store()
    original.racks[0].slots[0].items.extend([SlotItem(sku="w1", name="Water", price=99),
                                           SlotItem(sku="w2", name="WATER", price=149)])
    if len(product) == 160:
        original.racks[0].slots[0].items[-2].name = product
        original.racks[0].slots[0].items[-1].name = product + " longer name"
    before = original.model_dump_json()
    bad = {"name": "Sign test", "product": product, "promo": "NEW"}
    good = {**bad, "product": "Tea"}
    with pytest.raises(ValueError):
        to_design(_Draft.model_validate(bad), original, "USD", [])
    requests = []
    retry_later = False
    original_completion = llm_client.litellm.acompletion

    async def exercise():
        nonlocal retry_later

        def respond(request):
            requests.append(json.loads(request.content))
            result = good if retry_later or recovers and len(requests) > 1 else bad
            return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
                "model": "local-model", "choices": [{"index": 0, "finish_reason": "stop",
                    "message": {"role": "assistant", "content": json.dumps(result)}}]})

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            transport = AsyncOpenAI(api_key="offline", base_url="http://local.invalid/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original_completion(**{**kwargs, "client": transport, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/local-shelf-draft", api_base="http://local.invalid/v1",
                structured_output="json_schema", cache_dir=str(tmp_path)))

            async def draft():
                return await design_shelf_test(client, "Would a NEW sign help tea?", original, "USD", [])

            if not recovers:
                with pytest.raises(InstructorRetryException):
                    await draft()
                assert len(requests) == 2 and not list(tmp_path.rglob("*.json"))
                retry_later = True
            result = await draft()
            assert result.target_sku == result.rack_id == "tea"
            assert len(result.changes) == 1 and result.changes[0].promo == "NEW"
            assert not result.warnings
            assert await draft() == result
            assert client.get_usage().cached_requests == 1
            assert len(list(tmp_path.rglob("*.json"))) == 1

    asyncio.run(exercise())
    assert len(requests) == (2 if recovers else 3)
    feedback = json.dumps(requests[1]["messages"])
    assert ("several products" if product == "Water" else "not a product") in feedback
    assert original.model_dump_json() == before


@pytest.mark.parametrize("change", [
    {"package": "Missing pack", "promo": "SALE"},
    {"price": float("inf"), "promo": "SALE"},
    {"price": .004, "promo": "SALE"},
    {},
])
def test_reviewable_partial_drafts_keep_their_warnings_and_original_layout(change):
    original, calls = store(), []
    before = original.model_dump_json()

    class Model:
        async def generate_structured_async(self, schema, *args, **kwargs):
            calls.append(schema)
            return schema.model_validate({"name": "Review", "product": "Tea", **change})

    result = asyncio.run(design_shelf_test(Model(), "Try a change on tea", original, "USD", []))
    assert result.target_sku == "tea" and result.warnings
    assert [c.kind for c in result.changes] == (["promo"] if change else [])
    assert len(calls) == 1 and original.model_dump_json() == before
