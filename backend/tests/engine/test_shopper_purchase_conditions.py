"""Whole-trip and selected-shelf purchase predicates must both remain in a model filter."""

import asyncio
import json

import httpx
import pytest

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.customer import TimelineEvent
from store_emulator.domain.rack import Rack, Slot, SlotItem
from store_emulator.domain.types import Action
from store_emulator.engine.llm_client import LiteLLMClient
from store_emulator.engine.shopper_filter import find_shoppers
from tests.engine.test_shopper_filter_boundaries import STORE, customer


@pytest.mark.parametrize("provider", ["openai", "ollama"])
@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("bought", ["any", "yes", "no"])
@pytest.mark.parametrize("there", ["any", "yes", "no"])
def test_actual_sdk_intersects_trip_and_shelf_purchase_conditions(monkeypatch, tmp_path, provider, mode, bought, there):
    store = STORE.model_copy(update={"racks": [
        Rack(id=rid, type="shelf", shape=[[1]], position=(x, 1), rack_name=name,
             slots=[Slot(block=0, face="E", items=[SlotItem(sku=rid, name=name, price=100)])])
        for rid, x, name in [("tea", 1, "Tea"), ("snacks", 3, "Snacks")]]})
    customers = {}
    # A zero-total purchase is still a purchase. Nonvisitors must fail the shelf predicate.
    rows = [("empty", True, [], 0), ("elsewhere", True, ["snacks"], 100),
            ("free_elsewhere", True, ["snacks"], 0), ("there", True, ["tea"], 100),
            ("both", True, ["tea", "snacks"], 100), ("away_empty", False, [], 0),
            ("away_buyer", False, ["snacks"], 100)]
    for pid, stopped, purchases, price in rows:
        events = [TimelineEvent(elapsed_sec=0, x=0, y=0, action=Action.BROWSE, target_rack="tea")] if stopped else []
        events += [TimelineEvent(elapsed_sec=10 + i, x=0, y=0, action=Action.BUY,
                                 target_rack=rid, product_sku=rid, price=price) for i, rid in enumerate(purchases)]
        customers[pid] = customer(pid, spent=price * len(purchases)).model_copy(update={"timeline": events})
    before = [c.model_dump() for c in customers.values()]
    expected = {pid for pid, stopped, purchases, _ in rows if stopped
                and (bought == "any" or bool(purchases) == (bought == "yes"))
                and (there == "any" or ("tea" in purchases) == (there == "yes"))}
    payload = {"label": "Requested group", "stopped_at": ["Tea"], "bought": bought, "bought_there": there}
    calls = []

    def response(request):
        if request.url.path.endswith("/api/show"):
            return httpx.Response(200, request=request, json={"model_info": {}, "capabilities": ["completion"]})
        body = json.loads(request.content)
        calls.append(body)
        content = json.dumps(payload)
        if provider == "ollama":
            answer = {"model": "purchase-conditions", "done": True, "done_reason": "stop",
                      "message": {"role": "assistant", "content": content}, "prompt_eval_count": 10, "eval_count": 5}
        else:
            answer = {"id": "offline", "object": "chat.completion", "created": 0, "model": body["model"],
                      "choices": [{"index": 0, "finish_reason": "stop",
                                   "message": {"role": "assistant", "content": content}}]}
        return httpx.Response(200, request=request, json=answer)

    def send(self, request, *args, **kwargs): return response(request)
    async def asend(self, request, *args, **kwargs): return response(request)
    monkeypatch.setattr(httpx.Client, "send", send)
    monkeypatch.setattr(httpx.AsyncClient, "send", asend)
    client = LiteLLMClient(LLMConfig(model=f"{'ollama_chat' if provider == 'ollama' else 'openai'}/purchase-conditions",
        api_base="http://127.0.0.1:11434" if provider == "ollama" else "http://127.0.0.1:8081/v1",
        structured_output=mode, structured_sdk_retries=0, cache_dir=str(tmp_path)))

    async def exercise():
        for repeat in range(2):
            result = await find_shoppers(client, f"Tea visitors: trip purchase {bought}; shelf purchase {there}",
                                         customers, {}, store, "USD")
            assert set(result.persona_ids) == expected and result.total == 7
            assert not result.warnings
            assert ("Bought nothing" in result.criteria) == (bought == "no")
            assert len(calls) == 1 and client.get_usage().cached_requests == repeat
            assert [c.model_dump() for c in customers.values()] == before

    asyncio.run(exercise())
