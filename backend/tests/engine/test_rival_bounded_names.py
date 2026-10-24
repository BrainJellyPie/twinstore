"""Bounded rival aliases must retain the full names on both sides of a comparison."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.rack import SlotItem
from store_emulator.engine import llm_client
from store_emulator.engine.shelf_lab.rival import compare_rival
from store_emulator.engine.shelf_lab.rival_match import match_products
from tests.engine.test_rival_comparison_boundaries import pair


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("word", ["Tea", "녹차"])
@pytest.mark.parametrize("case", ["ours_unique", "rival_unique", "both_unique", "ours_collision", "rival_collision", "ours_exact", "short_prefix"])
def test_bounded_aliases_do_not_drop_or_replace_product_identities(monkeypatch, tmp_path, mode, word, case):
    prefix = (word * 160)[:160]
    rival_prefix = "R" * 160
    our_name = "Our Tea" if case in {"rival_unique", "rival_collision"} else prefix + " 500 ml"
    rival_name = rival_prefix + " 500 ml" if case in {"rival_unique", "rival_collision", "both_unique"} else "Different label"
    if case == "ours_exact":
        our_name = prefix
    store, capture = pair(our_name=our_name, rival_name=rival_name, our_price=200, rival_price=100)
    ours, rivals = [our_name], [rival_name]
    expected = {rival_name: our_name}
    if case == "ours_collision":
        ours.append(prefix)
        store.racks[0].slots[0].items.append(SlotItem(sku="different", name=prefix, price=50))
        expected = {}
    elif case == "rival_collision":
        rivals.append(rival_prefix)
        capture.items.append(capture.items[0].model_copy(update={"id": "different", "name": rival_prefix, "price": 400}))
        expected = {}
    elif case == "short_prefix":
        expected = {}
    payload = {"pairs": [{"ours": our_name[:159 if case == "short_prefix" else 160], "rival": rival_name[:160]}]}
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
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/rival-bounded", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            aliases = await match_products(client, rivals, ours)
            assert aliases == expected
            report = compare_rival(store, capture, aliases=aliases)
            assert report.matched == (1 if expected else 0)
            assert report.price_index == (pytest.approx(.5) if expected else None)
            assert report.suggested_pull_factor == (1.5 if expected else None)
            assert await match_products(client, rivals, ours) == aliases and len(calls) == 1
            assert client.get_usage().cached_requests == 1

    asyncio.run(exercise())
