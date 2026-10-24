"""A clipped long shelf-test target must not resolve to another shorter name."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.rack import SlotItem
from store_emulator.engine import llm_client
from store_emulator.engine.marketing.shelf_test_design import _Draft, design_shelf_test, to_design
from store_emulator.engine.marketing.variants import apply_changes
from tests.engine.test_layout_applied_changes import fixture


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("target", ["product", "package"])
@pytest.mark.parametrize("words", ["Tea organic leaf collection ", "茶 유기농 잎 컬렉션 "])
def test_long_name_does_not_select_a_shorter_word_match(monkeypatch, tmp_path, mode, target, words):
    store, _ = fixture("valid")
    full = (words * 30)[:190]
    short = words.split()[0]
    packages = []
    payload = {"name": "Shelf study", "product": "Tea", "price": 1.49}
    if target == "product":
        store.racks[1].slots[0].items[0].name = full
        store.racks[2].slots[0].items[0].name = short
        payload["product"] = full[:160]
    else:
        payload["package"] = full[:160]
        packages = [(short, "old-pack"), (full, "new-pack")]
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
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/shelf-bounded-names", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            before = store.model_dump_json()
            result = await design_shelf_test(client, "Change the named product", store, "USD", packages)
            assert result.target_sku == "tea" and result.rack_id == "source"
            edited, applied, warnings = apply_changes(store, result.changes, package_uris={"new-pack": "new.png", "old-pack": "old.png"})
            assert len(applied) == (2 if target == "package" else 1) and not warnings and not result.warnings
            tea = edited.racks[1].slots[0].items[0]
            assert tea.price == 149 and edited.racks[2].slots[0].items[0].price == 99
            if target == "package":
                assert tea.image_url == "new.png"
            assert await design_shelf_test(client, "Change the named product", store, "USD", packages) == result
            assert len(calls) == 1 and client.get_usage().cached_requests == 1
            assert store.model_dump_json() == before

    asyncio.run(exercise())


@pytest.mark.parametrize("target", ["product", "package"])
@pytest.mark.parametrize("second", ["long", "exact", "same-id"])
def test_ambiguous_prefix_never_falls_back_to_an_exact_boundary_name(target, second):
    store, _ = fixture("valid")
    prefix = "Tea " + "x" * 156
    full = prefix + " first"
    other = prefix if second == "exact" else prefix + " second"
    packages = []
    payload = {"name": "Study", "product": "Tea", "promo": "NEW"}
    if target == "product":
        items = store.racks[1].slots[0].items
        items[0].name = full
        items.append(SlotItem(sku="tea" if second == "same-id" else "other", name=other, price=199))
        payload["product"] = prefix
    else:
        packages = [(full, "new-pack"), (other, "new-pack" if second == "same-id" else "other-pack")]
        payload["package"] = prefix
    draft = _Draft.model_validate(payload)
    if target == "product" and second != "same-id":
        with pytest.raises(ValueError):
            to_design(draft, store, "USD", packages)
    else:
        result = to_design(draft, store, "USD", packages)
        assert result.target_sku == "tea"
        changed_packs = [c.asset_id for c in result.changes if c.kind == "package"]
        assert changed_packs == (["new-pack"] if target == "package" and second == "same-id" else [])
        assert bool(result.warnings) == (target == "package" and second != "same-id")
