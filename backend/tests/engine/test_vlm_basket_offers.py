"""The vision shopper's basket names the purchased offer, not every catalog alias of its SKU."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI

from store_emulator.domain.action import CustomerAction
from store_emulator.domain.behavior import BehaviorPattern
from store_emulator.domain.config import LLMConfig, SimulationConfig
from store_emulator.domain.rack import Rack, Slot, SlotItem
from store_emulator.domain.store import Store
from store_emulator.domain.types import Action, Face, Weekday
from store_emulator.engine import llm_client
from store_emulator.engine.perception import render_face
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.customer_executor import execute_decision
from store_emulator.engine.simulation.engines.vlm_glance import VLMGlanceEngine
from tests.engine.test_llm_engine_offline import _context, _persona


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("origin", ["planned", "impulse"])
@pytest.mark.parametrize("placement", ["block", "level", "remote_rack"])
@pytest.mark.parametrize("alias", ["Basic tea", "Premium tea"])
def test_later_glance_sees_only_the_exact_planned_or_impulse_offer(monkeypatch, tmp_path, mode, origin, placement, alias):
    wrong = Slot(block=0, face=Face.N, level=3, items=[SlotItem(sku="tea", name=alias, price=100)])
    selected = Slot(block=1 if placement == "block" else 0, face=Face.N, level=4 if placement == "level" else 3,
                    items=[SlotItem(sku="tea", name="Premium tea", price=700)])
    offers = Rack(id="a-offers", rack_name="Offers", type="shelf", position=(3, 1),
                  shape=[[1, 1]] if placement == "block" else [[1]],
                  slots=[selected] if placement == "remote_rack" else [wrong, selected])
    observer = Rack(id="z-observer", rack_name="Observer", type="shelf", position=(6, 1), shape=[[1]],
                    slots=[Slot(block=0, face=Face.N, level=3, items=[SlotItem(sku="fruit", name="Fruit", price=200)])])
    store = Store(id="basket", name="Basket", type="shop", grid_size=(11, 10), racks=[offers, observer,
        Rack(id="in", type="entrance", position=(0, 0), shape=[[1]]),
        Rack(id="out", type="exit", position=(9, 0), shape=[[1]]),
        Rack(id="till", type="counter", position=(8, 2), shape=[[1]])])
    if placement == "remote_rack":
        store.racks.append(Rack(id="remote", type="shelf", position=(9, 8), shape=[[1]], slots=[wrong]))
    cfg = SimulationConfig(budget_tolerance=None, max_quantity_per_line=1)
    cfg.engines.vlm_glance.plan_policy = "rule"
    cfg.engines.vlm_glance.glance_policy = "all"
    cfg.engines.vlm_glance.glance_order = "rack"
    cfg.engines.vlm_glance.max_glances = 6
    cfg.engines.vlm_glance.shuffle_marks = False
    cfg.engines.vlm_glance.buy_scale = 1
    cfg.engines.vlm_glance.weight_by_level = False
    cfg.engines.vlm_glance.image_width = 256
    context = _context(store, _persona(10000))
    context.behavior_patterns = [BehaviorPattern(id="purposeful", name="Shop", description="", grammar="",
        browse_required_before_buy=False, max_products=4)]
    view = render_face(offers, Face.N, width=256)
    badge = next(item.mark for item in view.items if item.slot.block == selected.block and item.slot.level == selected.level)
    original, prompts = llm_client.litellm.acompletion, []

    def respond(request):
        body = json.loads(request.content)
        user = next(m["content"][0]["text"] for m in body["messages"] if m["role"] == "user")
        prompts.append(user)
        take = origin == "impulse" and "Passing: the Offers" in user
        payload = {"number": badge if take else 0, "product": "", "interest": 10 if take else 0}
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(payload)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/vlm-basket-offers", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            finder = AStarPathFinder()
            engine = VLMGlanceEngine(client, finder, cfg)
            plan, middle = engine._begin_plan(context)
            if origin == "planned":
                assert engine.add_planned_buy(store, plan, middle, offers, selected, selected.items[0], "planned tea", quantity=1)
            else:
                middle.append(CustomerAction(nav="path", action=Action.BROWSE, target=(3, 0), face=Face.N))
            engine.close_plan(store, plan, middle)
            monkeypatch.setattr(engine, "_plan", lambda _: plan)
            decision = await engine.decide_actions(context)
            result = execute_decision(store, "P1", Weekday.MON, "12:00:00", decision, finder, 1, max_quantity=1)
            assert [(p.product_name, p.price, p.origin) for p in result.purchases] == [("Premium tea", 700, origin)]
            assert result.total_spent == 700 and result.timeline[-1].action == Action.EXIT
            later = next(user for user in prompts if "Passing: the Observer" in user)
            assert "Already in basket: Premium tea." in later
            assert "Basic tea" not in later

    asyncio.run(exercise())
