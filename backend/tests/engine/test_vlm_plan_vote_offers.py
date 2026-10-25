"""Entry-plan votes distinguish offers and cannot collide on delimited SKU text."""

import asyncio
import json
from itertools import permutations

import httpx
import pytest
from openai import AsyncOpenAI

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.types import Weekday
from store_emulator.engine import llm_client
from store_emulator.engine.llm_router import EnsembleLLMClient
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.customer_executor import execute_decision
from store_emulator.engine.simulation.engines.vlm_glance import VLMGlanceEngine
from store_emulator.engine.simulation.engines.vlm_glance.planning import PlanMatch, match_plan_item
from store_emulator.engine.simulation.engines.vlm_glance.prompt import EntryDecision, PlannedItem, combine_plan_votes
from tests.engine.test_purchase_quantity_limits import context_for
from tests.engine.test_vlm_plan import _config
from tests.engine.test_vlm_plan_category_disambiguation import fixture


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("order", list(permutations(range(3))))
@pytest.mark.parametrize("same_sku", [False, True])
@pytest.mark.parametrize("reverse", [False, True])
def test_http_majority_retains_its_offer_and_supporter_quantity(monkeypatch, tmp_path, mode, order, same_sku, reverse):
    store, _ = fixture(same_sku, reverse)
    before = store.model_dump_json()
    votes = [("Snacks", 5), ("Milk", 1), ("Milk", 3)]
    original, calls = llm_client.litellm.acompletion, []

    def respond(request):
        body = json.loads(request.content)
        member = int(body["model"].rsplit("-", 1)[1])
        calls.append(member)
        category, qty = votes[member]
        payload = {"enter": True, "items": [{"category": category, "product": "Original", "qty": qty}]}
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop", "message": {
                "role": "assistant", "content": json.dumps(payload)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            clients = [llm_client.LiteLLMClient(LLMConfig(model=f"openai/vlm-plan-vote-member-{i}",
                api_base="http://127.0.0.1:8081/v1", structured_output=mode, cache_dir=str(tmp_path))) for i in range(3)]
            ensemble = EnsembleLLMClient([(str(i), 1, clients[i]) for i in order], mode="vote")
            paths = AStarPathFinder()
            engine = VLMGlanceEngine(ensemble, paths, _config(entrance_image=False, max_glances=0).model_copy(
                update={"budget_tolerance": None}))
            for repeat in range(2):
                decision = await engine.decide_actions(context_for(store, 7))
                result = execute_decision(store, "shopper", Weekday.MON, "12:00:00", decision, paths, 1)
                assert len(result.purchases) == 1
                buy = result.purchases[0]
                assert (buy.target_rack, buy.product_sku, buy.price, buy.product_level, buy.quantity) == (
                    "milk", "shared" if same_sku else "milk", 700, 3, 2)
                assert result.total_spent == 1400
                assert engine.plan_log[-1].items == (("Milk", "Original", 2),)
                assert engine.plan_log[-1].source == "vote" and engine.plan_log[-1].agreement == 1
                assert sorted(calls) == [0, 1, 2]
                assert all(c.get_usage().cached_requests == repeat for c in clients)
            assert store.model_dump_json() == before

    asyncio.run(exercise())


def test_offer_identity_is_order_independent_and_preserves_exact_sku_text():
    store, engine = fixture(True, False)
    catalog = engine._catalog_for(store)
    assert PlanMatch("exact", tuple(catalog)).key == PlanMatch("category", tuple(reversed(catalog))).key
    assert PlanMatch("exact", tuple(catalog)).key == PlanMatch("exact", tuple(catalog + catalog)).key
    assert PlanMatch("unresolved", ()).key == ""
    item = PlannedItem(category="Milk", product="Original")
    assert match_plan_item(item, catalog).key == match_plan_item(PlannedItem(category="MILK", product="original"), catalog).key
    assert match_plan_item(item, catalog).key != match_plan_item(PlannedItem(category="Snacks", product="Original"), catalog).key


@pytest.mark.parametrize("field", ["rack", "block", "face", "level", "sku"])
def test_each_resolved_placement_dimension_distinguishes_votes(field):
    store, engine = fixture(True, False)
    rack, slot, item, category_words, product_words = engine._catalog_for(store)[0]
    other_rack, other_slot, other_item = rack.model_copy(deep=True), slot.model_copy(deep=True), item.model_copy(deep=True)
    if field == "rack": other_rack.id += "|elsewhere"
    elif field == "block": other_slot.block += 1
    elif field == "face": other_slot.face = type(slot.face).S
    elif field == "level": other_slot.level += 1
    else: other_item.sku = "SHARED"
    first = PlanMatch("exact", ((rack, slot, item, category_words, product_words),))
    second = PlanMatch("exact", ((other_rack, other_slot, other_item, category_words, product_words),))
    assert first.key != second.key


def test_a_literal_pipe_in_one_sku_cannot_merge_two_different_product_choices():
    store, engine = fixture(False, False)
    catalog = engine._catalog_for(store)
    rack, slot, item, words, names = catalog[0]
    combined = PlanMatch("exact", ((rack, slot, item.model_copy(update={"sku": "a|b"}), words, names),))
    separate = PlanMatch("category", tuple((rack, slot, item.model_copy(update={"sku": sku}), words, names) for sku in ("a", "b")))
    keys = {"Combined": combined.key, "Separate": separate.key}
    assert keys["Combined"] != keys["Separate"]
    answers = [("a", EntryDecision(enter=True, items=[PlannedItem(product="Combined")])),
               ("b", EntryDecision(enter=True, items=[PlannedItem(product="Separate")])),
               ("c", EntryDecision(enter=True, items=[PlannedItem(product="Separate")]))]
    result, agreement = combine_plan_votes(answers, lambda item: keys[item.product])
    assert [item.product for item in result.items] == ["Separate"] and agreement == 1
