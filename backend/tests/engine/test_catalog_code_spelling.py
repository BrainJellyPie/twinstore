"""A context-recovery shortlist uses supplied offer codes, not canonical SKU guesses."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI
from pydantic import ValidationError

from store_emulator.domain.config import LLMConfig, SimulationConfig
from store_emulator.domain.rack import SlotItem
from store_emulator.domain.types import Action, Weekday
from store_emulator.engine import llm_client
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.customer_executor import execute_decision
from store_emulator.engine.simulation.engines.pattern_intent_impulse import stage2_intent
from store_emulator.engine.simulation.engines.pattern_intent_impulse.engine import PatternIntentImpulseEngine
from tests.engine.test_llm_engine_offline import _context, _persona
from tests.engine.test_llm_impulse_exposure import fixture


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("ordering", ["planned", "nearest"])
@pytest.mark.parametrize("spelling", ["lowercase", "whitespace", "mixed"])
@pytest.mark.parametrize("collision", ["none", "exact", "case_only"])
def test_http_shortlist_spelling_recovers_exact_offer_after_context_overflow(monkeypatch, tmp_path, mode, ordering, spelling, collision):
    store, intent = fixture()
    store.racks[0].slots[0].items = [SlotItem(sku=f"seen{i}", name=f"Tea {i}", price=100 + i * 100) for i in range(6)]
    if collision != "none":
        store.racks[0].slots[0].items[1].sku = "@P1" if collision == "exact" else "@p1"
    code = next(key for key, item in stage2_intent.catalog_records(store).items() if item.sku == "seen0")
    said = code.lower() if spelling == "lowercase" else f"\u3000{code}\n" if spelling == "whitespace" else f" {code.lower()} "
    good = intent.model_dump(mode="json")
    good["actions"].insert(-1, {"nav": "path", "action": "buy", "product_sku": code, "quantity": 2})
    original, calls = llm_client.litellm.acompletion, []

    def respond(request):
        body = json.loads(request.content)
        system = body["messages"][0]["content"]
        if "## 행동 패턴 목록" in system:
            kind, answer = "pattern", {"pattern_id": "exploratory"}
        elif "## 후보 상품 선택" in system:
            kind, answer = "selection", {"codes": [said]}
        elif "세렌디피티" in system:
            kind, answer = "impulse", {"actions": []}
        elif "## 후보 상품 범위" in system:
            kind, answer = "intent", good
        else:
            calls.append("full")
            return httpx.Response(400, request=request, json={"error": {"type": "exceed_context_size_error",
                "message": "request (8500 tokens) exceeds the available context size (8192 tokens)"}})
        calls.append(kind)
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(answer)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/shortlist-spelling", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            paths = AStarPathFinder()
            engine = PatternIntentImpulseEngine(client, paths, SimulationConfig(route_ordering=ordering))
            before = store.model_dump_json()
            for repeat in range(2):
                decision = await engine.decide_actions(_context(store, _persona(10000)))
                assert decision.trace["catalog_recovery"] == {"selected_codes": [code], "selected_skus": ["seen0"]}
                result = execute_decision(store, "P1", Weekday.MON, "12:00:00", decision, paths, 1)
                assert [(p.product_sku, p.quantity, p.price) for p in result.purchases] == [("seen0", 2, 100)]
                assert result.total_spent == 200 and sum(e.action == Action.PAY for e in result.timeline) == 1
                assert result.timeline[-1].action == Action.EXIT and store.model_dump_json() == before
                assert calls.count("selection") == 1 and calls.count("full") == 1 + repeat
                assert client.get_usage().cached_requests == 4 * repeat
            saved = [json.loads(p.read_text())["result"] for p in tmp_path.rglob("*.json")]
            assert {"codes": [code]} in saved

    asyncio.run(exercise())


def test_ambiguous_or_unknown_codes_still_fail_and_exact_codes_remain_distinct():
    records = {"@Pa1": SlotItem(sku="a", name="A", price=100), "@pA1": SlotItem(sku="b", name="B", price=200)}
    schema = stage2_intent.catalog_selection_model(records, 2, required=True)
    assert schema(codes=["@Pa1", "@pA1"]).codes == ["@Pa1", "@pA1"]
    for invalid in ["@pa1", "@P2", "P1", "@P1-extra"]:
        with pytest.raises(ValidationError):
            schema(codes=[invalid])


def test_known_spelling_variants_keep_existing_shortlist_deduplication():
    records = {f"@P{i}": SlotItem(sku=str(i), name=str(i), price=100) for i in range(1, 4)}
    schema = stage2_intent.catalog_selection_model(records, 3, required=True)
    assert schema(codes=["@P1", " @p1 ", "@p2"]).codes == ["@P1", "@P2"]
