"""Automatically drafted free offers must match manually entered zero-price changes."""

import asyncio
import json

import httpx
import pytest

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.marketing import ExperimentRequest, ShelfTestRequest
from store_emulator.engine.llm_client import LiteLLMClient
from store_emulator.engine.marketing.experiment_design import design_experiment
from store_emulator.engine.marketing.shelf_test_design import design_shelf_test
from store_emulator.engine.marketing.variants import apply_changes
from tests.engine.test_shelf_design_boundaries import store


@pytest.mark.parametrize("provider", ["openai", "ollama"])
@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("surface", ["shelf", "experiment"])
@pytest.mark.parametrize("currency", ["USD", "KRW"])
@pytest.mark.parametrize("price", [0, -0.0, None, 0.0001])
def test_actual_sdk_free_price_survives_drafting_request_and_application(monkeypatch, tmp_path, provider, mode, surface, currency, price):
    source = store().model_copy(update={"currency": currency})
    before = source.model_dump()
    changes = [{"kind": "price", "product": "Tea", "price": price}, {"kind": "promo", "product": "Tea", "promo": "SALE"}]
    payload = ({"name": "Free tea", "product": "Tea", "price": price, "promo": "SALE"} if surface == "shelf" else
               {"name": "Free tea", "variants": [{"name": "Free offer", "changes": changes}]})
    calls = []

    def response(request):
        if request.url.path.endswith("/api/show"):
            return httpx.Response(200, request=request, json={"model_info": {}, "capabilities": ["completion"]})
        body = json.loads(request.content)
        calls.append(body)
        content = json.dumps(payload)
        if provider == "ollama":
            answer = {"model": "free-design", "done": True, "done_reason": "stop",
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
    client = LiteLLMClient(LLMConfig(model=f"{'ollama_chat' if provider == 'ollama' else 'openai'}/free-design",
        api_base="http://127.0.0.1:11434" if provider == "ollama" else "http://127.0.0.1:8081/v1",
        structured_output=mode, structured_sdk_retries=0, cache_dir=str(tmp_path)))

    async def exercise():
        for repeat in range(2):
            args = (client, "Test an explicitly free Tea offer with a SALE sign", source, currency, [])
            if surface == "shelf":
                result = await design_shelf_test(*args)
                request = ShelfTestRequest(setup_id="s", rack_id=result.rack_id, target_sku=result.target_sku, changes=result.changes)
                changes = request.changes
            else:
                result = await design_experiment(*args)
                request = ExperimentRequest(setup_id="s", variants=result.variants, focus_skus=result.focus_skus)
                changes = request.variants[0].changes
            prices = [c.price for c in changes if c.kind == "price"]
            assert prices == ([0] if price == 0 else [])
            changed, applied, warnings = apply_changes(source, changes, minor_per_major=1 if currency == "KRW" else 100)
            item = changed.racks[0].slots[0].items[0]
            assert item.price == (0 if price == 0 else 199) and item.promo == "SALE"
            if price == 0:
                assert item.regular_price == 199 and not result.warnings
            assert applied and not warnings and source.model_dump() == before
            assert len(calls) == 1 and client.get_usage().cached_requests == repeat

    asyncio.run(exercise())


@pytest.mark.parametrize("surface", ["shelf", "experiment"])
def test_free_price_alone_is_an_applicable_design(surface):
    from store_emulator.engine.marketing import experiment_design, shelf_test_design

    source = store()
    if surface == "shelf":
        draft = shelf_test_design._Draft(name="Free tea", product="Tea", price=0)
        result = shelf_test_design.to_design(draft, source, "USD", [])
        changes = result.changes
    else:
        draft = experiment_design._Draft.model_validate({"name": "Free tea", "variants": [
            {"name": "Free offer", "changes": [{"kind": "price", "product": "Tea", "price": 0}]}]})
        result = experiment_design.to_design(draft, source, "USD", [])
        changes = result.variants[0].changes
    changed, applied, warnings = apply_changes(source, changes)
    assert len(changes) == 1 and changes[0].price == 0
    assert changed.racks[0].slots[0].items[0].price == 0
    assert source.racks[0].slots[0].items[0].price == 199
    assert applied and not warnings and not result.warnings
