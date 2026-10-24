"""Optional descriptions must not discard applicable automatic edits."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI
from pydantic import ValidationError

from store_emulator.domain.config import LLMConfig
from store_emulator.engine import llm_client
from store_emulator.engine.layout_edit import _EditDraft, draft_layout_edit
from store_emulator.engine.marketing.experiment_design import _Draft, design_experiment
from store_emulator.engine.marketing.variants import apply_changes
from tests.engine.test_layout_applied_changes import fixture


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("kind", ["layout", "experiment"])
@pytest.mark.parametrize("annotation", ["null", "omitted", "provided"])
@pytest.mark.parametrize("currency,price,minor", [("USD", 1.49, 149), ("KRW", 1490, 1490)])
def test_optional_annotations_preserve_combined_edits_and_focus(monkeypatch, tmp_path, mode, kind, annotation, currency, price, minor):
    store, move = fixture("valid")
    changes = [{"kind": "price", "product": "Tea", "price": price}, move]
    payload = {"name": "New layout", **({"changes": changes} if kind == "layout" else {
        "variants": [{"name": "Price and placement", "changes": changes}]})}
    text = "차 가격과 진열 위치 변경"
    if annotation != "omitted":
        payload["summary" if kind == "layout" else "rationale"] = None if annotation == "null" else text
        if kind == "experiment":
            payload["focus_products"] = None if annotation == "null" else ["Water"]
    original, calls = llm_client.litellm.acompletion, []

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop", "message": {
                "role": "assistant", "content": json.dumps(payload)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/edit-annotations", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            before = store.model_dump_json()

            async def draft():
                if kind == "layout":
                    return await draft_layout_edit(client, "Change the price and move Tea", store, currency)
                return await design_experiment(client, "Compare the changes", store, currency, [])

            result = await draft()
            operations = result.changes if kind == "layout" else result.variants[0].changes
            edited, applied, warnings = apply_changes(store, operations, minor_per_major=1 if currency == "KRW" else 100)
            assert len(applied) == 2 and not warnings and not result.warnings
            placements = [(r.id, s.level, i.price) for r in edited.racks for s in r.slots for i in s.items if i.sku == "tea"]
            assert placements == [("target", 3, minor)]
            narrative = result.summary if kind == "layout" else result.rationale
            assert narrative == (text if annotation == "provided" else "")
            if kind == "experiment":
                assert result.focus_skus == (["water"] if annotation == "provided" else ["tea"])
            assert await draft() == result and len(calls) == 1 and client.get_usage().cached_requests == 1
            assert store.model_dump_json() == before

    asyncio.run(exercise())


@pytest.mark.parametrize("kind", ["layout", "experiment"])
def test_required_edits_and_malformed_nonnull_annotations_stay_invalid(kind):
    model = _EditDraft if kind == "layout" else _Draft
    change = {"kind": "price", "product": "Tea", "price": 1.49}
    field = "summary" if kind == "layout" else "rationale"
    operations = "changes" if kind == "layout" else "variants"
    payload = {"name": "Draft", operations: [change] if kind == "layout" else [{"name": "Variant", "changes": [change]}]}
    for bad in ({**payload, operations: None}, {**payload, operations: []}, {**payload, "name": None},
                *({**payload, field: value} for value in [[], {}, 123, "x" * 501])):
        with pytest.raises(ValidationError):
            model.model_validate(bad)
    if kind == "experiment":
        assert model.model_validate({**payload, "rationale": None, "focus_products": ["Tea"]}).focus_products == ["Tea"]
        assert model.model_validate({**payload, "rationale": "Keep this explanation", "focus_products": None}).rationale == "Keep this explanation"
        for value in ["Tea", {}, [None], [123], ["Tea"] * 9]:
            with pytest.raises(ValidationError):
                model.model_validate({**payload, "focus_products": value})
