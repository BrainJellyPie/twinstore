"""Research prompts count direct purchases as shelf stops, once per shopper."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI

from store_emulator.domain.action import CustomerAction
from store_emulator.domain.config import LLMConfig
from store_emulator.domain.engine import EngineDecision
from store_emulator.domain.types import Action, Face, Weekday
from store_emulator.engine import llm_client
from store_emulator.engine.interview import run_text, suggest_group_questions
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.customer_executor import execute_decision
from tests.engine.test_llm_impulse_exposure import fixture


def trip(store, identifier, actions):
    decision = EngineDecision(engine_type="pattern_intent_impulse", actions=[
        CustomerAction(nav="path", target=(0, 3), action=Action.ENTER), *actions,
        CustomerAction(nav="path", target=(0, 2), action=Action.PAY),
        CustomerAction(nav="leave", action=Action.EXIT),
    ])
    return execute_decision(store, identifier, Weekday.MON, "12:00:00", decision, AStarPathFinder(), 1)


def pick(target=(2, 2), sku="seen"):
    return CustomerAction(nav="path", target=target, face=Face.S, action=Action.BUY, product_sku=sku, quantity=3)


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("case,counts", [
    ("direct", {"Near shelf": (1, 1)}), ("mixed", {"Near shelf": (2, 1)}),
    ("repeated", {"Near shelf": (1, 1)}), ("two_buyers", {"Near shelf": (2, 2)}),
    ("different", {"Near shelf": (1, 0), "Far shelf": (1, 1)}), ("walk", {}), ("invalid", {}),
])
def test_executed_visits_reach_research_prompt_without_losing_direct_buys(monkeypatch, tmp_path, mode, case, counts):
    store, _ = fixture()
    store.racks[0].rack_name, store.racks[1].rack_name = "Near shelf", "Far shelf"
    browse = CustomerAction(nav="path", target=(2, 2), face=Face.S, action=Action.BROWSE)
    groups = {
        "direct": [[pick()]], "mixed": [[pick()], [browse]], "repeated": [[browse, browse, pick(), pick()]],
        "two_buyers": [[pick()], [pick()]], "different": [[browse, pick((10, 2), "unseen")]],
        "walk": [[CustomerAction(nav="path", target=(2, 2), action=Action.MOVE)]],
        "invalid": [[pick(sku="absent")]],
    }[case]
    customers = [trip(store, str(i), actions) for i, actions in enumerate(groups)]
    if case in {"direct", "two_buyers"}:
        assert all(c.units_bought == 3 and not any(e.action == Action.BROWSE for e in c.timeline) for c in customers)
    summary = run_text(customers, store, "USD")
    original, calls = llm_client.litellm.acompletion, []

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant",
                "content": json.dumps({"questions": [{"question": "What influenced your shelf choice?", "segment": "all"}]})}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/interview-purchase-stops", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            result = await suggest_group_questions(client, summary)
            assert await suggest_group_questions(client, summary) == result and len(calls) == 1
            user = calls[0]["messages"][1]["content"]
            for name, (stops, buyers) in counts.items():
                assert f"{name} {stops} / {buyers}" in user
            assert ("Shelves where shoppers stopped" in user) is bool(counts)
            if case == "mixed":
                assert "stopped at a shelf but left empty-handed: 1" in user
            if case == "direct":
                # Same totals and person, different purchase location: the question
                # generator must see new shelf evidence instead of reusing its cache.
                moved = run_text([trip(store, "0", [pick((10, 2), "unseen")])], store, "USD")
                await suggest_group_questions(client, moved)
                assert len(calls) == 2
                assert "Far shelf 1 / 1" in calls[1]["messages"][1]["content"]
                assert "Near shelf 1 / 1" not in calls[1]["messages"][1]["content"]

    asyncio.run(exercise())
