"""Similar names are candidates for model matching, never proof of equal products."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI

from store_emulator.domain.capture import CaptureItem
from store_emulator.domain.config import LLMConfig
from store_emulator.domain.rack import SlotItem
from store_emulator.engine import llm_client
from store_emulator.engine.shelf_lab.rival import compare_rival, unmatched_names
from store_emulator.engine.shelf_lab.rival_match import match_products
from tests.engine.test_rival_comparison_boundaries import pair


DIFFERENT = [
    ("Coca-Cola Original 500ml", "Coca-Cola Original 1500ml"),
    ("Organic Vanilla Yogurt 500g", "Organic Banana Yogurt 500g"),
    ("오리지널 요거트 500ml", "오리지널 요거트 1500ml"),
    ("Organic Tea Pack 6", "Organic Tea Pack 16"),
    ("TwinStore Organic Tea 500ml", "WinStore Organic Tea 500ml"),
    ("Organic Milk 1% 500ml", "Organic Milk 2% 500ml"),
]


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("ours,theirs", DIFFERENT)
@pytest.mark.parametrize("reverse", [False, True])
def test_different_variants_reach_model_and_do_not_contaminate_prices(monkeypatch, tmp_path, mode, ours, theirs, reverse):
    store, capture = pair(our_name=ours, rival_name=theirs, our_price=200, rival_price=400)
    store.racks[0].slots[0].items.append(SlotItem(sku="coffee", name="Coffee", price=200))
    capture.items.append(CaptureItem(id="coffee", band=0, level=1, order=1, name="Coffee", price=180, labeled=True))
    if reverse:
        capture.items.reverse()
        store.racks[0].slots[0].items.reverse()
    before = store.model_dump(), capture.model_dump()
    missing, listed = unmatched_names(store, capture)
    assert missing == [theirs]
    original, requests = llm_client.litellm.acompletion, []

    def respond(request):
        body = json.loads(request.content)
        requests.append(body)
        assert theirs in body["messages"][-1]["content"] and ours in body["messages"][-1]["content"]
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop", "message": {
                "role": "assistant", "content": json.dumps({"pairs": [{"rival": theirs, "ours": ""}]})}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/rival-similar", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            aliases = await match_products(client, missing, listed)
            assert aliases == {}
            for selected in (None, aliases):
                report = compare_rival(store, capture, aliases=selected)
                assert report.matched == 1 and report.price_index == pytest.approx(0.9)
                assert report.suggested_pull_factor == 1.111 and report.overlap == pytest.approx(1 / 3, abs=0.0001)
                assert report.only_rival == [theirs] and report.only_ours == [ours]
                assert [row.name for row in report.prices] == ["Coffee"]
            assert await match_products(client, missing, listed) == aliases and len(requests) == 1
            assert (store.model_dump(), capture.model_dump()) == before

    asyncio.run(exercise())


@pytest.mark.parametrize("ours,theirs", [
    ("Coca-Cola 500ml", "COCA COLA 500ML"), ("Tea 500ml", "Ｔｅａ　５００ｍｌ"),
    ("오리지널 요거트 500ml", "  오리지널   요거트 500ml  "), ("🍵", "🍵"),
])
def test_normalized_exact_names_still_need_no_model(ours, theirs):
    store, capture = pair(our_name=ours, rival_name=theirs)
    assert unmatched_names(store, capture)[0] == []
    assert compare_rival(store, capture).price_index == 1


def test_confirmed_alias_can_resolve_a_typo():
    ours, theirs = "Organic Vanilla Yogurt 500g", "Organic Vanila Yogurt 500g"
    store, capture = pair(our_name=ours, rival_name=theirs, our_price=200, rival_price=100)
    assert unmatched_names(store, capture)[0] == [theirs]
    assert compare_rival(store, capture).price_index is None
    assert compare_rival(store, capture, aliases={theirs: ours}).price_index == 0.5
