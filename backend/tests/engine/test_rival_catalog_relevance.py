"""Relevant references after the catalog limit must still reach model matching."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.rack import SlotItem
from store_emulator.engine import llm_client
from store_emulator.engine.shelf_lab.rival import compare_rival, unmatched_names
from store_emulator.engine.shelf_lab.rival_match import match_products
from tests.engine.test_rival_comparison_boundaries import pair


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("count", [299, 300, 301])
@pytest.mark.parametrize("first", [False, True])
@pytest.mark.parametrize("common,ours,theirs", [
    ("Everyday tea", "Saffron tea 500 ml", "Saffron tea 500ml"),
    ("일반 차음료", "제주유자 차음료 500 ml", "제주유자 차음료 500ml"),
])
def test_specific_product_reaches_price_comparison_regardless_of_shelf_order(
    monkeypatch, tmp_path, mode, count, first, common, ours, theirs,
):
    store, capture = pair(our_name=ours, rival_name=theirs, our_price=200, rival_price=100)
    rack = store.racks[0]
    items = [SlotItem(sku=f"ordinary-{i}", name=f"{common} {i}", price=400) for i in range(count - 1)]
    items.insert(0 if first else len(items), rack.slots[0].items[0])
    rack.shape = [[1] * ((len(items) + 3) // 4)]
    store.grid_size = (128, 8)
    rack.slots = [rack.slots[0].model_copy(update={"block": i // 4, "items": items[i:i + 4]})
                  for i in range(0, len(items), 4)]
    missing, listed = unmatched_names(store, capture)
    assert missing == [theirs] and len(listed) == count
    assert compare_rival(store, capture).matched == 0  # Word similarity alone never confirms identity.
    before = store.model_dump(), capture.model_dump()
    original, requests = llm_client.litellm.acompletion, []

    def respond(request):
        body = json.loads(request.content)
        user = next(message["content"] for message in body["messages"] if message["role"] == "user")
        names = [line.removeprefix("- ") for line in user.split("\n\nRival products:", 1)[0].splitlines()[1:]]
        requests.append(names)
        assert len(names) == min(count, 300) and len(set(names)) == len(names)
        # Scripted model copies a known answer only when supplied with that reference.
        content = json.dumps({"pairs": [{"rival": theirs, "ours": ours if ours in names else ""}]})
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": content}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/rival-references", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            for repeat in range(2):
                aliases = await match_products(client, missing, listed)
                assert aliases == {theirs: ours}
                report = compare_rival(store, capture, aliases=aliases)
                assert report.matched == 1 and report.price_index == pytest.approx(.5)
                assert report.suggested_pull_factor == 1.5 and report.prices[0].name == ours
                assert len(requests) == 1 and client.get_usage().cached_requests == repeat
                assert (store.model_dump(), capture.model_dump()) == before

    asyncio.run(exercise())
