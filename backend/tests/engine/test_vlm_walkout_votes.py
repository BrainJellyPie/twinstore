"""Products left in a rejected entrance plan cannot cast purchase or quantity votes."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI

from store_emulator.domain.config import LLMConfig, SimulationConfig
from store_emulator.domain.types import Action, Weekday
from store_emulator.engine import llm_client
from store_emulator.engine.llm_router import EnsembleLLMClient
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.customer_executor import execute_decision
from store_emulator.engine.simulation.engines.vlm_glance import VLMGlanceEngine
from tests.engine.test_llm_engine_offline import _context, _persona
from tests.engine.test_llm_impulse_exposure import fixture


# (enter, quantity of "seen"), None is a failed provider, quantity 0 is browsing only.
CASES = [
    ([(True, 0), (False, 3)], 0, True, 0.5),
    ([(True, 1), (True, 0), (False, 3)], 0, True, 2 / 3),
    ([(True, 1), (True, 1), (False, 3), (False, 3)], 1, True, 0.5),
    ([(True, 1), (False, 3), (False, 3)], 0, False, 2 / 3),
    ([(True, 0), (False, 3), None], 0, True, 0.5),
    ([(True, 1), (True, 3), (True, 0)], 2, True, 1.0),
]


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("image", [False, True])
@pytest.mark.parametrize("votes,quantity,entered,agreement", CASES,
    ids=["tie-browse", "minority-item", "quantity-contamination", "majority-walkout", "failed-member", "valid-support"])
def test_walkout_items_never_create_or_inflate_actual_purchases(monkeypatch, tmp_path, mode, image, votes, quantity, entered, agreement):
    store, _ = fixture()
    before = store.model_dump_json()
    context = _context(store, _persona(1000))
    context.behavior_patterns = [p for p in context.behavior_patterns if p.id == "purposeful"]
    config = SimulationConfig(budget_tolerance=1, max_quantity_per_line=3)
    config.engines.vlm_glance.max_glances = 0
    config.engines.vlm_glance.entrance_image = image
    original, calls = llm_client.litellm.acompletion, []

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        vote = votes[int(body["model"].rsplit("-", 1)[1])]
        if vote is None:
            return httpx.Response(503, request=request, json={"error": {"message": "offline provider unavailable", "type": "server_error"}})
        enter, qty = vote
        answer = {"enter": enter, "mission": "shop" if enter else "turn away",
                  "items": [{"product": "seen", "qty": qty}] if qty else []}
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(answer)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            members = [(f"member-{i}", 1.0, llm_client.LiteLLMClient(LLMConfig(model=f"openai/walkout-vote-{i}",
                api_base="http://127.0.0.1:8081/v1", structured_output=mode, cache_dir=str(tmp_path)))) for i in range(len(votes))]
            ensemble = EnsembleLLMClient(members, mode="vote")
            finder = AStarPathFinder()
            engine = VLMGlanceEngine(ensemble, finder, config)
            for repeat in range(2):
                decision = await engine.decide_actions(context)
                result = execute_decision(store, "P1", Weekday.MON, "12:00:00", decision, finder, 1, max_quantity=3)
                assert [(p.product_sku, p.quantity, p.price) for p in result.purchases] == ([('seen', quantity, 100)] if quantity else [])
                assert result.total_spent == quantity * 100
                assert sum(e.action == Action.PAY for e in result.timeline) == int(quantity > 0)
                assert result.timeline[-1].action == Action.EXIT
                assert engine.plan_log[-1].enter is entered
                assert engine.plan_log[-1].agreement == pytest.approx(agreement)
                assert len(calls) == len(votes) + repeat * votes.count(None)
            assert ensemble.get_usage().cached_requests == len(votes) - votes.count(None)
            assert store.model_dump_json() == before

    asyncio.run(exercise())
