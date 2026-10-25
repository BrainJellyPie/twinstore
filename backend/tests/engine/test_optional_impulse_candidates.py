"""An absent optional shortlist must not erase an already planned purchase."""

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
@pytest.mark.parametrize("shape", ["null", "empty", "omitted"])
def test_http_optional_shortlist_preserves_planned_trip_and_cached_absence(monkeypatch, tmp_path, mode, ordering, shape):
    store, intent = fixture()
    store.racks[0].slots[0].items = [SlotItem(sku=f"seen{i}", name=f"Tea {i}", price=100 + i * 100) for i in range(6)]
    code = next(key for key, item in stage2_intent.catalog_records(store).items() if item.sku == "seen0")
    original, calls = llm_client.litellm.acompletion, []

    def respond(request):
        body = json.loads(request.content)
        system = body["messages"][0]["content"]
        if "## 행동 패턴 목록" in system:
            kind, answer = "pattern", {"pattern_id": "exploratory"}
        elif "## 충동 후보 선택" in system:
            kind = "selection"
            answer = {} if shape == "omitted" else {"codes": None if shape == "null" else []}
        elif "세렌디피티" in system:
            calls.append("full")
            return httpx.Response(400, request=request, json={"error": {"type": "exceed_context_size_error",
                "message": "request (8500 tokens) exceeds the available context size (8192 tokens)"}})
        else:
            kind, answer = "intent", intent.model_dump(mode="json")
            answer["actions"].insert(-1, {"nav": "path", "action": "buy", "product_sku": code, "quantity": 2})
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
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/optional-impulse-candidates", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            paths = AStarPathFinder()
            engine = PatternIntentImpulseEngine(client, paths, SimulationConfig(route_ordering=ordering))
            before = store.model_dump_json()
            for repeat in range(2):
                decision = await engine.decide_actions(_context(store, _persona(10000)))
                assert decision.trace["impulse_catalog_recovery"] == {"selected_codes": [], "selected_skus": []}
                result = execute_decision(store, "P1", Weekday.MON, "12:00:00", decision, paths, 1)
                assert [(p.product_sku, p.quantity, p.origin) for p in result.purchases] == [("seen0", 2, "planned")]
                assert result.total_spent == 200 and sum(e.action == Action.PAY for e in result.timeline) == 1
                assert result.timeline[-1].action == Action.EXIT and store.model_dump_json() == before
                assert calls.count("selection") == 1 and calls.count("full") == 1 + repeat
                assert client.get_usage().cached_requests == 3 * repeat
                if repeat == 0 and shape == "null":
                    # A cached optional null receives the same normalization.
                    entries = [p for p in tmp_path.rglob("*.json") if json.loads(p.read_text())["result"] == {"codes": []}]
                    assert len(entries) == 1
                    entries[0].write_text(json.dumps({"result": {"codes": None}}))

    asyncio.run(exercise())


@pytest.mark.parametrize("required", [False, True])
@pytest.mark.parametrize("invalid", ["", {}, False, 1, [None], ["unknown"]])
def test_malformed_non_null_candidate_lists_remain_invalid(required, invalid):
    records = {"@P1": SlotItem(sku="tea", name="Tea", price=100)}
    schema = stage2_intent.catalog_selection_model(records, 4, required=required)
    with pytest.raises(ValidationError):
        schema.model_validate_json(json.dumps({"codes": invalid}), strict=True)


def test_null_is_only_an_absent_optional_list_and_grammar_still_asks_for_an_array():
    records = {"@P1": SlotItem(sku="tea", name="Tea", price=100)}
    primary = stage2_intent.catalog_selection_model(records, 4, required=True)
    optional = stage2_intent.catalog_selection_model(records, 4)
    for data in [{}, {"codes": None}]:
        with pytest.raises(ValidationError):
            primary.model_validate_json(json.dumps(data), strict=True)
        assert optional.model_validate_json(json.dumps(data), strict=True).codes == []
    assert optional.model_json_schema()["properties"]["codes"]["type"] == "array"
    assert primary.model_validate_json('{"codes": []}', strict=True).codes == []
