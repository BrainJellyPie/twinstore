"""Small starter tasks must not invite more new categories than remain available."""

import asyncio
import json
from collections import Counter

import httpx
import pytest
from openai import AsyncOpenAI

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.starter_fill import StarterRack
from store_emulator.engine import llm_client
from store_emulator.engine.layout_gen.catalog import CATALOG, catalog_slot_item
from store_emulator.engine.starter_selection import select_starter_products
from tests.engine.test_starter_selection import empty_store


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("count", [17, 24, 99, 100])
@pytest.mark.parametrize("second_new", [1, 3, 7])
@pytest.mark.parametrize("category_limit", [16, 24, 40])
def test_near_full_category_budget_keeps_every_rack_without_invalid_global_choices(monkeypatch, tmp_path,
                                                                                 mode, count, second_new, category_limit):
    original = llm_client.litellm.acompletion
    calls, small = [], []
    allowed = sorted(CATALOG)[:40]

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        system = body["messages"][0]["content"]
        payload = json.loads(next(m["content"] for m in body["messages"] if m["role"] == "user"))
        if "correction" in payload:
            answer = payload["correction"]["previous_response"]
        elif "expected_rack_ids" in payload:
            answer = {"groups": [{"category": allowed[0], "rack_ids": ["invented_section_999"]}]}
        elif "racks" in payload:
            previous = payload["already_selected_categories"]
            choices = [row["id"] for row in payload["categories"]]
            new = [key for key in choices if key not in previous]
            size = len(payload["racks"])
            small.append((len(previous), size))
            if len(previous) == 8:
                values = new[:second_new] + [previous[0]] * (size - second_new)
            else:
                values = new[:size] + [choices[0]] * max(0, size - len(new))
            answer = {"choices": values}
        else:
            assert "EACH listed category" in system
            answer = {"groups": [{"category": key, "skus": [products[0]["sku"]]}
                                 for key, products in payload["categories"].items()]}
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(answer)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/starter-category-budget", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            racks = [StarterRack(id=f"선반/{i}", name=f"Section {i} (20 racks)", type="shelf", available_slots=2)
                     for i in range(count)]
            store = empty_store()
            before = store.model_dump()
            result = await select_starter_products(client, store, racks, "동네 주민", allowed_categories=set(allowed),
                                                   category_limit=category_limit)
            assert Counter(row.rack_id for row in result) == Counter(r.id for r in racks)
            maximum = min(category_limit, count, len(allowed))
            assert len({row.category for row in result}) == min(maximum, 8 + second_new + count - 16)
            assert all(row.skus and set(row.skus) <= {catalog_slot_item(item, "USD").sku for item in CATALOG[row.category]}
                       for row in result)
            assert all(size <= (maximum - previous if previous < maximum and len(allowed) > maximum else 8)
                       for previous, size in small)
            assert len(calls) == 3 + len(small)  # Two bulk attempts, small tasks, one product selection.
            previous = len(calls)
            assert await select_starter_products(client, store, racks, "동네 주민", allowed_categories=set(allowed),
                                                 category_limit=category_limit) == result
            assert len(calls) == previous and store.model_dump() == before

    asyncio.run(exercise())
