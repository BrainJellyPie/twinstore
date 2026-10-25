"""A missing operational sign must not silently become a different promotion."""

import asyncio
import json

import httpx
import pytest
from instructor.core.exceptions import InstructorRetryException

from store_emulator.domain.config import LLMConfig
from store_emulator.engine.layout_edit import draft_layout_edit
from store_emulator.engine.llm_client import LiteLLMClient
from store_emulator.engine.marketing.experiment_design import design_experiment
from store_emulator.engine.marketing.variants import apply_changes
from tests.engine.test_layout_applied_changes import fixture


@pytest.mark.parametrize("kind", ["layout", "experiment"])
@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("bad", ["missing", "", " \t\r\n", None])
@pytest.mark.parametrize("corrected", [False, True])
def test_missing_promotion_text_retries_or_stops_without_inventing_sale(monkeypatch, tmp_path, kind, mode, bad, corrected):
    store, _ = fixture("valid")
    before = store.model_dump_json()
    calls = []
    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        change = {"kind": " PrOmO ", "product": "Tea"}
        if corrected and len(calls) > 1:
            change["promo"] = "1+1"
        elif bad != "missing":
            change["promo"] = bad
        payload = {"name": "Buy one get one", **({"changes": [change]} if kind == "layout" else {
            "variants": [{"name": "Buy one get one", "changes": [change]}]})}
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(payload)}}]})
    async def asend(self, request, *args, **kwargs): return respond(request)
    monkeypatch.setattr(httpx.AsyncClient, "send", asend)
    client = LiteLLMClient(LLMConfig(model="openai/promo-text", api_base="http://127.0.0.1:8081/v1", api_key="offline",
        structured_output=mode, cache_dir=str(tmp_path)))
    async def draft():
        if kind == "layout":
            return await draft_layout_edit(client, "Put a 1+1 sign on Tea", store, "USD")
        return await design_experiment(client, "Test a 1+1 sign on Tea", store, "USD", [])
    async def exercise():
        if not corrected:
            with pytest.raises(InstructorRetryException):
                await draft()
            assert not list(tmp_path.glob("*/*.json"))
        else:
            result = await draft()
            changes = result.changes if kind == "layout" else result.variants[0].changes
            assert len(changes) == 1 and changes[0].promo == "1+1"
            changed, applied, warnings = apply_changes(store, changes)
            assert len(applied) == 1 and not warnings
            assert all(item.promo == "1+1" for rack in changed.racks for slot in rack.slots for item in slot.items if item.sku == "tea")
            assert await draft() == result and client.get_usage().cached_requests == 1
        assert len(calls) == 2 and store.model_dump_json() == before
    asyncio.run(exercise())


@pytest.mark.parametrize("kind", ["layout", "experiment"])
def test_old_cached_missing_promo_cannot_bypass_the_new_validation(monkeypatch, tmp_path, kind):
    store, _ = fixture("valid")
    client = LiteLLMClient(LLMConfig(model="openai/cached-promo", api_base="http://127.0.0.1:8081/v1", api_key="offline",
        structured_output="json_schema", cache_dir=str(tmp_path)))
    calls = []
    def payload(sign):
        change = {"kind": "promo", "product": "Tea", "promo": sign}
        return {"name": "Sign", **({"changes": [change]} if kind == "layout" else {"variants": [{"name": "Sign", "changes": [change]}]})}
    original_cache_get = client._cache_get
    def seed_cache(path, schema):
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"result": payload("")}))
        return original_cache_get(path, schema)
    monkeypatch.setattr(client, "_cache_get", seed_cache)
    async def asend(self, request, *args, **kwargs):
        calls.append(request)
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": "cached-promo", "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(payload("1+1"))}}]})
    monkeypatch.setattr(httpx.AsyncClient, "send", asend)
    async def exercise():
        result = (await draft_layout_edit(client, "Put a 1+1 sign on Tea", store, "USD") if kind == "layout" else
                  await design_experiment(client, "Test a 1+1 sign on Tea", store, "USD", []))
        changes = result.changes if kind == "layout" else result.variants[0].changes
        assert changes[0].promo == "1+1" and len(calls) == 1 and client.get_usage().cached_requests == 0
    asyncio.run(exercise())
