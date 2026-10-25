"""Unusable automatic layout and experiment edits are corrected before response caching."""

import asyncio
import json

import httpx
import pytest
from instructor.core.exceptions import InstructorRetryException
from openai import AsyncOpenAI

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.rack import Rack, Slot, SlotItem
from store_emulator.domain.store import Store
from store_emulator.engine import llm_client
from store_emulator.engine.layout_edit import _EditDraft, draft_layout_edit, to_edit
from store_emulator.engine.marketing.experiment_design import _Draft, design_experiment, to_design


@pytest.fixture
def store():
    return Store(id="s", name="Store", type="convenience", grid_size=(8, 8), racks=[
        Rack(id="r", rack_name="Drinks", type="shelf", shape=[[1]], position=(3, 3), slots=[
            Slot(block=0, face="N", level=1, items=[SlotItem(sku="tea", name="Tea", price=199),
                SlotItem(sku="w1", name="Water", price=99), SlotItem(sku="w2", name="WATER", price=149)])])])


INVALID = [
    pytest.param("USD", {"kind": "move", "product": "Tea", "level": 3, "category": "Drinks"}, "no unique shelf",
                 id="shelf-sent-as-category"),
    pytest.param("USD", {"kind": "promo", "product": "Invented tea"}, "no unique product", id="unknown-product"),
    pytest.param("USD", {"kind": "promo", "product": "Water"}, "ambiguous", id="ambiguous-product"),
    pytest.param("USD", {"kind": "move", "product": "Tea", "shelf": "Nowhere"}, "no unique shelf", id="unknown-shelf"),
    pytest.param("USD", {"kind": "discount", "product": "Tea", "percent": 20}, "negative percent", id="positive-discount"),
    pytest.param("USD", {"kind": "discount", "product": "Tea"}, "negative percent", id="missing-discount"),
    pytest.param("USD", {"kind": "category_price", "category": "Drinks"}, "category and a percent", id="missing-percent"),
    pytest.param("USD", {"kind": "price", "product": "Tea", "price": None}, "no new price", id="missing-price"),
    pytest.param("USD", {"kind": "price", "product": "Tea", "price": -1}, "no new price", id="negative-price"),
    pytest.param("USD", {"kind": "price", "product": "Tea", "price": float("inf")}, "no new price", id="infinite-price"),
    pytest.param("USD", {"kind": "price", "product": "Tea", "price": 1e308}, "safe integer", id="huge-price"),
    pytest.param("USD", {"kind": "price", "product": "Tea", "price": .004}, "rounds to zero", id="sub-cent"),
    pytest.param("JPY", {"kind": "price", "product": "Tea", "price": .49}, "rounds to zero", id="sub-yen"),
]


@pytest.mark.parametrize("currency,change,feedback", INVALID)
@pytest.mark.parametrize("kind", ["layout", "experiment"])
@pytest.mark.parametrize("recovers", [False, True])
def test_unusable_edits_get_bounded_correction_without_poisoning_cache(
    tmp_path, monkeypatch, store, currency, change, feedback, kind, recovers,
):
    original_store = store.model_dump_json()
    good_change = {"kind": "promo", "product": "Tea", "promo": "NEW"}

    def payload(changes):
        return ({"name": "New signs", "changes": changes} if kind == "layout" else
                {"name": "New signs", "variants": [{"name": "Signs", "changes": changes}]})

    bad, good = payload([change]), payload([good_change])
    with pytest.raises(ValueError):
        if kind == "layout":
            to_edit(_EditDraft.model_validate(bad), store, currency)
        else:
            to_design(_Draft.model_validate(bad), store, currency, [])
    requests = []
    retry_later = False
    original = llm_client.litellm.acompletion

    async def exercise():
        nonlocal retry_later

        def respond(request):
            requests.append(json.loads(request.content))
            answer = good if retry_later or recovers and len(requests) > 1 else bad
            return httpx.Response(200, request=request, json={
                "id": "offline-layout", "object": "chat.completion", "created": 0, "model": "local-model",
                "choices": [{"index": 0, "finish_reason": "stop", "message": {
                    "role": "assistant", "content": json.dumps(answer)}}]})

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            transport = AsyncOpenAI(api_key="offline-test", base_url="http://local.invalid/v1",
                                    http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": transport, "api_key": "offline-test", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/local-layout-test", api_base="http://local.invalid/v1",
                structured_output="json_schema", cache_dir=str(tmp_path), seed=0))

            async def draft():
                if kind == "layout":
                    return await draft_layout_edit(client, "New sign on tea", store, currency)
                return await design_experiment(client, "New sign on tea", store, currency, [])

            if not recovers:
                with pytest.raises(InstructorRetryException):
                    await draft()
                assert len(requests) == 2
                assert not list(tmp_path.rglob("*.json"))
                retry_later = True
            result = await draft()
            changes = result.changes if kind == "layout" else result.variants[0].changes
            assert len(changes) == 1 and changes[0].sku == "tea" and changes[0].promo == "NEW"
            assert not result.warnings
            assert await draft() == result
            assert client.get_usage().cached_requests == 1
            assert len(list(tmp_path.rglob("*.json"))) == 1

    asyncio.run(exercise())
    assert len(requests) == (2 if recovers else 3)
    assert feedback in json.dumps(requests[1]["messages"]).lower()
    assert store.model_dump_json() == original_store


@pytest.mark.parametrize("kind", ["layout", "experiment"])
def test_usable_partial_edits_keep_warnings_without_retrying_or_mutating_the_store(store, kind):
    before = store.model_dump_json()
    calls = []
    changes = [{"kind": "promo", "product": "Tea", "promo": "NEW"},
               {"kind": "price", "product": "Invented", "price": 1}]

    class Model:
        async def generate_structured_async(self, schema, *args, **kwargs):
            calls.append(schema)
            payload = ({"name": "Signs", "changes": changes} if kind == "layout" else
                       {"name": "Signs", "variants": [{"name": "Signs", "changes": changes}]})
            return schema.model_validate(payload)

    result = asyncio.run(draft_layout_edit(Model(), "New sign on tea", store, "USD") if kind == "layout" else
                         design_experiment(Model(), "New sign on tea", store, "USD", []))
    accepted = result.changes if kind == "layout" else result.variants[0].changes
    assert len(accepted) == 1 and accepted[0].sku == "tea"
    assert any("Invented" in warning for warning in result.warnings)
    assert len(calls) == 1 and store.model_dump_json() == before
