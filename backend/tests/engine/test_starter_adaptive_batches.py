"""Ordered recovery must adapt when even eight rack rows overwhelm the model."""

import asyncio
import json
from collections import Counter

import httpx
import pytest
from instructor.core.exceptions import FailedAttempt, InstructorRetryException
from litellm.exceptions import BadRequestError
from openai import AsyncOpenAI

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.starter_fill import StarterRack
from store_emulator.engine import llm_client
from store_emulator.engine.layout_gen.catalog import CATALOG, catalog_slot_item
from store_emulator.engine.starter_selection import select_starter_products
from tests.engine.test_starter_selection import empty_store
from tests.engine.test_starter_selection_small_tasks import SmallTaskModel


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("count,capacity", [(2, 1), (9, 3), (24, 1), (100, 3)])
@pytest.mark.parametrize("fault", ["short", "unknown", "context", "truncated"])
def test_small_tasks_shrink_without_losing_rows_or_the_category_budget(monkeypatch, tmp_path, mode, count, capacity, fault):
    allowed = sorted(CATALOG)[:24]
    racks = [StarterRack(id=rid, name=f"Shelf {i} (20 racks)", type="fridge" if i % 2 else "shelf", available_slots=2)
             for i, rid in enumerate(["진열대 🌿", "__proto__", *[f"section/{i}" for i in range(count - 2)]])]
    original = llm_client.litellm.acompletion
    calls, accepted, rejected = [], [], []

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        payload = json.loads(next(m["content"] for m in body["messages"] if m["role"] == "user"))
        finish = "stop"
        if "expected_rack_ids" in payload:
            answer = {"groups": [{"category": allowed[0], "rack_ids": ["invented_section_999"]}]}
        elif "racks" in payload:
            rows = payload["racks"]
            previous = payload["already_selected_categories"]
            offered = [c["id"] for c in payload["categories"]]
            assert set(offered) <= set(allowed) and len(previous) <= 16
            if len(previous) == 16:
                assert set(offered) == set(previous)
            if len(rows) > capacity:
                rejected.append(len(rows))
                if fault == "context":
                    return httpx.Response(400, request=request, json={"error": {"code": 400,
                        "message": "request (9000 tokens) exceeds the available context size (8192 tokens)",
                        "type": "exceed_context_size_error"}})
                if fault == "truncated":
                    finish = "length"
                answer = {"choices": ["invented"] * len(rows) if fault == "unknown" else [offered[0]]}
            else:
                accepted.append(([r["name"] for r in rows], len(previous)))
                new = [c for c in offered if c not in previous]
                values = (new or offered)[:len(rows)]
                answer = {"choices": values}
        else:
            answer = {"groups": [{"category": key, "skus": [products[0]["sku"]]}
                                 for key, products in payload["categories"].items()]}
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": finish,
                "message": {"role": "assistant", "content": json.dumps(answer)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/starter-adaptive-batches",
                api_base="http://127.0.0.1:8081/v1", structured_output=mode, cache_dir=str(tmp_path)))
            store = empty_store("KRW")
            before = store.model_dump_json()

            async def select():
                return await select_starter_products(client, store, racks, "동네 주민; exclude alcohol",
                    allowed_categories=set(allowed), product_limits={key: 1 for key in allowed})

            result = await select()
            assert Counter(r.rack_id for r in result) == Counter(r.id for r in racks)
            assert len({r.category for r in result}) == min(count, 16)
            assert [name for names, _ in accepted for name in names] == [r.name for r in racks]
            assert all(len(names) <= capacity for names, _ in accepted)
            assert len(set(rejected)) <= 3
            assert all(len(r.skus) == 1 and set(r.skus) <= {catalog_slot_item(p, "KRW").sku for p in CATALOG[r.category]}
                       for r in result)
            assert len(calls) <= 3 + 2 * len(set(rejected)) + len(accepted)
            accepted_count = len(accepted)
            assert await select() == result
            # Invalid schema/context responses are never cached; every valid leaf is reused.
            assert len(accepted) == accepted_count and client.get_usage().cached_requests >= accepted_count + 1
            assert store.model_dump_json() == before

    asyncio.run(exercise())


@pytest.mark.parametrize("error", [TimeoutError("offline"), ValueError("bad provider configuration"),
    BadRequestError("unsupported server setting", model="openai/local", llm_provider="openai"),
    InstructorRetryException("failed", n_attempts=1, total_usage=0, failed_attempts=[FailedAttempt(1, TimeoutError("offline"))])])
def test_unrelated_small_task_failures_do_not_shrink_or_continue(error):
    class Offline(SmallTaskModel):
        async def generate_structured_async(self, schema, system, user, **kwargs):
            if "choices" in schema.model_fields:
                self.calls.append((schema, json.loads(user), system))
                raise error
            return await super().generate_structured_async(schema, system, user, **kwargs)

    model = Offline()
    racks = [StarterRack(id=str(i), name=f"Shelf {i}", type="shelf", available_slots=2) for i in range(24)]
    with pytest.raises(type(error)):
        asyncio.run(select_starter_products(model, empty_store(), racks, ""))
    assert len(model.calls) == 3 and len(model.calls[-1][1]["racks"]) == 8


def test_a_late_irreducible_row_stops_before_products_or_partial_publication():
    class Partial(SmallTaskModel):
        async def generate_structured_async(self, schema, system, user, **kwargs):
            payload = json.loads(user)
            if "choices" in schema.model_fields and "racks" in payload:
                self.calls.append((schema, payload, system))
                good = len(payload["racks"]) == 1 and payload["racks"][0]["name"] != "Bad shelf"
                return schema.model_validate({"choices": ["home_coffee_tea"] if good else []})
            return await super().generate_structured_async(schema, system, user, **kwargs)

    model = Partial(product_fault=False)
    store = empty_store()
    before = store.model_dump_json()
    racks = [StarterRack(id=str(i), name=name, type="shelf", available_slots=2)
             for i, name in enumerate(["Good shelf", "Bad shelf", "Later shelf"])]
    with pytest.raises(ValueError):
        asyncio.run(select_starter_products(model, store, racks, ""))
    small = [p["racks"] for s, p, _ in model.calls if "choices" in s.model_fields]
    assert [len(rows) for rows in small] == [3, 1, 1]
    assert small[-1][0]["name"] == "Bad shelf"
    assert not any("maximum_products_per_category" in p for _, p, _ in model.calls)
    assert store.model_dump_json() == before
