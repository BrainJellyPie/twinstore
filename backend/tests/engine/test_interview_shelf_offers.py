"""Interviews retain distinct prices and promotions for the same product SKU."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI

from store_emulator.domain.action import CustomerAction
from store_emulator.domain.config import LLMConfig
from store_emulator.domain.rack import Slot
from store_emulator.domain.types import Action, Face
from store_emulator.engine import llm_client
from store_emulator.engine.interview import ask_shopper, build_journey, suggest_follow_ups
from store_emulator.engine.prompting import display_price
from tests.engine.test_interview_purchase_stops import trip
from tests.engine.test_llm_engine_offline import _persona
from tests.engine.test_llm_impulse_exposure import fixture


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("operation", ["answer", "follow_up"])
@pytest.mark.parametrize("currency", ["USD", "KRW"])
@pytest.mark.parametrize("field,initial,changed", [
    ("price", 199, 299), ("regular_price", 349, 449),
    ("promo", "Member offer", "Weekend offer"), ("name", "Tea original pack", "Tea new pack"),
])
def test_executed_stop_retains_each_offer_and_invalidates_changed_evidence_cache(
    monkeypatch, tmp_path, mode, operation, currency, field, initial, changed,
):
    store, _ = fixture()
    first = store.racks[0].slots[0].items[0]
    first.name, first.price = "Tea", 249
    store.racks[0].slots[0].items.append(first.model_copy(deep=True))
    second = first.model_copy(update={field: initial})
    store.racks[0].slots += [Slot(block=0, face=Face.S, level=2, items=[second]),
        Slot(block=0, face=Face.N, level=3, items=[first.model_copy(update={"promo": "Unseen offer", "price": 999})])]
    customer = trip(store, "P1", [CustomerAction(nav="path", target=(2, 2), face=Face.S, action=Action.BROWSE)])
    modified = store.model_copy(deep=True)
    setattr(modified.racks[0].slots[1].items[0], field, changed)
    before = store.model_dump_json(), modified.model_dump_json(), customer.model_dump_json()
    journeys = [build_journey("offers", customer, _persona(), source, currency) for source in (store, modified)]
    original, calls = llm_client.litellm.acompletion, []

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        payload = ({"answer": "I considered the available offer.", "steps": []} if operation == "answer"
                   else {"questions": ["How did the offer affect your choice?"]})
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(payload)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/interview-shelf-offers", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))

            async def run(journey, source):
                if operation == "answer":
                    reply = await ask_shopper(client, journey, source, [], "How did the tea offer affect your choice?")
                    return reply.model_dump()
                return await suggest_follow_ups(client, journey, source, [])

            for index, (journey, source, value) in enumerate(zip(journeys, (store, modified), (initial, changed), strict=True), 1):
                result = await run(journey, source)
                assert await run(journey, source) == result
                assert len(calls) == index and client.get_usage().cached_requests == index
                user = calls[-1]["messages"][1]["content"]
                marker = display_price(value, currency) if field in ("price", "regular_price") else value
                assert marker in user and "Unseen offer" not in user
                assert f"Tea {display_price(249, currency)}" in user
                assert len(journey.shelves["near"]) == 2
                assert {getattr(item, field) for item in journey.shelves["near"]} == {getattr(first, field), value}
                assert list(journey.shelves) == ["near"]
            assert before == (store.model_dump_json(), modified.model_dump_json(), customer.model_dump_json())

    asyncio.run(exercise())


@pytest.mark.parametrize("reverse", [False, True])
def test_exact_copies_collapse_but_different_offers_survive_slot_order(reverse):
    store, _ = fixture()
    item = store.racks[0].slots[0].items[0]
    second = item.model_copy(update={"price": 90, "regular_price": 100, "promo": "Offer"})
    store.racks[0].slots[0].items = [item, item.model_copy(), second, second.model_copy()]
    if reverse:
        store.racks[0].slots[0].items.reverse()
    customer = trip(store, "P1", [CustomerAction(nav="path", target=(2, 2), face=Face.S, action=Action.BROWSE)])
    journey = build_journey("offers", customer, _persona(), store, "USD")
    assert {(entry.sku, entry.price, entry.regular_price, entry.promo) for entry in journey.shelves["near"]} == {
        ("seen", 100, 0, ""), ("seen", 90, 100, "Offer")}
    assert len(journey.shelves["near"]) == 2
