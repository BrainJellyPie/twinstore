"""Optional fields do not discard a valid price, pack or sign study."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI
from pydantic import ValidationError

from store_emulator.domain.config import LLMConfig
from store_emulator.engine import llm_client
from store_emulator.engine.marketing.shelf_test_design import _Draft, design_shelf_test
from store_emulator.engine.marketing.variants import apply_changes
from tests.engine.test_layout_applied_changes import fixture


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("change", [{"price": 1.49}, {"package": "New pack"}, {"promo": "NEW"}, {}])
@pytest.mark.parametrize("annotations", ["null", "provided"])
def test_unused_fields_preserve_shelf_study_effects_and_cache(monkeypatch, tmp_path, mode, change, annotations):
    store, _ = fixture("valid")
    absent = None if annotations == "null" else ""
    payload = dict(name="Study", product="Tea", price=None, package=absent, promo=absent,
        rationale=None if annotations == "null" else "Compare this change",
        age_groups=None if annotations == "null" else ["30s"])
    payload.update(change)
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
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/shelf-optional-annotations", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            before = store.model_dump_json()

            async def draft():
                return await design_shelf_test(client, "Compare the requested change", store, "USD", [("New pack", "new-pack")])

            result = await draft()
            assert result.target_sku == "tea" and result.rack_id == "source"
            assert result.age_groups == ([] if annotations == "null" else ["30s"])
            assert result.rationale == ("" if annotations == "null" else "Compare this change")
            assert bool(result.warnings) == (not change)
            edited, applied, warnings = apply_changes(store, result.changes, package_uris={"new-pack": "new.png"})
            assert len(applied) == len(change) and not warnings
            tea = edited.racks[1].slots[0].items[0]
            assert tea.price == (149 if "price" in change else 199)
            assert tea.promo == change.get("promo", "")
            if "package" in change:
                assert tea.image_url == "new.png"
            if not change:
                assert edited.model_dump_json() == before
            assert await draft() == result and len(calls) == 1 and client.get_usage().cached_requests == 1
            assert store.model_dump_json() == before

    asyncio.run(exercise())


@pytest.mark.parametrize("field,value", [
    ("product", None), ("name", None), ("package", []), ("package", 123),
    ("promo", {}), ("promo", "X" * 13), ("rationale", []), ("rationale", "X" * 501),
    ("age_groups", "30s"), ("age_groups", [None]), ("age_groups", ["70s"]),
])
def test_optional_defaults_do_not_accept_wrong_types_or_missing_targets(field, value):
    with pytest.raises(ValidationError):
        _Draft.model_validate({"name": "Study", "product": "Tea", field: value})
