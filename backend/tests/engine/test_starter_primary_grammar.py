"""The initial local-model grammar must exclude invented sections and categories."""

import asyncio
import json
from collections import Counter

import httpx
import pytest
from openai import AsyncOpenAI

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.starter_fill import StarterRack
from store_emulator.engine import llm_client
from store_emulator.engine.starter_selection import select_starter_products
from tests.engine.test_starter_selection import empty_store


@pytest.mark.parametrize("ids", [
    ["section_0"],
    ["section_0", "section_20"],
    ["진열대 🌿", "a/b", "quote\"", "back\\slash", "Case", "case", "__proto__"],
    [f"section_{i}" for i in range(8)],
    [f"section_{i}" for i in range(99)],
    [f"section_{i}" for i in range(100)],
])
@pytest.mark.parametrize("allowed", [{"home_coffee_tea"}, {"home_coffee_tea", "dairy"}])
def test_first_http_request_constrains_exact_ids_and_reuses_successful_cache(monkeypatch, tmp_path, ids, allowed):
    requests = []
    original_completion = llm_client.litellm.acompletion

    def respond(request):
        body = json.loads(request.content)
        requests.append(body)
        response_schema = body["response_format"]["json_schema"]
        schema = response_schema["schema"]
        context = json.loads(body["messages"][-1]["content"])
        if response_schema["name"] == "CategorySelection":
            group = schema["$defs"][schema["properties"]["groups"]["items"]["$ref"].rsplit("/", 1)[1]]
            fields = group["properties"]
            # Assert the actual OpenAI wire contract, not just the prompt or Pydantic class.
            assert set(fields["category"].get("enum", [])) == allowed
            assert set(fields["rack_ids"]["items"].get("enum", [])) == set(ids)
            assert "section_999" not in fields["rack_ids"]["items"]["enum"]
            assert "occupied" not in fields["rack_ids"]["items"]["enum"]
            answer = {"groups": [{"category": sorted(allowed)[0], "rack_ids": ids}]}
        else:
            assert response_schema["name"] == "ProductSelection"
            answer = {"groups": [{"category": key, "skus": [products[0]["sku"]]}
                                  for key, products in context["categories"].items()]}
        return httpx.Response(200, request=request, json={
            "id": "offline", "object": "chat.completion", "created": 0, "model": "local",
            "choices": [{"index": 0, "finish_reason": "stop",
                         "message": {"role": "assistant", "content": json.dumps(answer)}}],
        })

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            transport = AsyncOpenAI(api_key="offline", base_url="http://local.invalid/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original_completion(**{**kwargs, "client": transport, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/local-grammar", api_base="http://local.invalid/v1",
                structured_output="json_schema", cache_dir=str(tmp_path)))
            store = empty_store()
            before = store.model_dump()
            racks = [StarterRack(id=rid, name="선반 (20 racks)", type="shelf", available_slots=2) for rid in ids]
            racks += [StarterRack(id="occupied", name="Keep", type="shelf", available_slots=4, reason="Occupied"),
                      StarterRack(id="blocked", name="Blocked", type="shelf", available_slots=0)]
            first = await select_starter_products(client, store, racks, "동네 주민", allowed_categories=allowed)
            second = await select_starter_products(client, store, racks, "동네 주민", allowed_categories=set(reversed(sorted(allowed))))
            assert Counter(row.rack_id for row in first) == Counter(ids)
            assert all(row.category in allowed and len(row.skus) == 1 for row in first)
            assert first == second and client.get_usage().cached_requests == 2
            assert store.model_dump() == before

    asyncio.run(exercise())
    assert len(requests) == 2


def test_concurrent_requests_keep_their_own_identifier_grammars():
    class Inspect:
        async def generate_structured_async(self, schema, system, user, **kwargs):
            context = json.loads(user)
            await asyncio.sleep(0)
            if "racks" in context:
                contract = schema.model_json_schema()
                group = contract["$defs"][contract["properties"]["groups"]["items"]["$ref"].rsplit("/", 1)[1]]
                ids = context["expected_rack_ids"]
                keys = [row["id"] for row in context["categories"]]
                assert set(group["properties"]["category"].get("enum", [])) == set(keys)
                assert set(group["properties"]["rack_ids"]["items"].get("enum", [])) == set(ids)
                return schema.model_validate({"groups": [{"category": keys[0], "rack_ids": ids}]})
            fields = schema.model_json_schema()["properties"]["groups"]
            assert fields["minItems"] == fields["maxItems"] == len(context["categories"])
            alternatives = fields["items"]["anyOf"]
            assert {group["properties"]["category"]["const"] for group in alternatives} == set(context["categories"])
            for group in alternatives:
                key = group["properties"]["category"]["const"]
                assert group["properties"]["skus"]["items"]["enum"] == [p["sku"] for p in context["categories"][key]]
                assert group["properties"]["skus"]["maxItems"] == context["maximum_products_per_category"][key]
            return schema.model_validate({"groups": [{"category": key, "skus": [products[0]["sku"]]}
                                                     for key, products in context["categories"].items()]})

    async def exercise():
        return await asyncio.gather(*[
            select_starter_products(Inspect(), empty_store(),
                [StarterRack(id=rid, name="Shelf", type="shelf", available_slots=2)], "", allowed_categories={key})
            for rid, key in [("section_0", "home_coffee_tea"), ("section_10", "dairy")]
        ])

    first, second = asyncio.run(exercise())
    assert [(r.rack_id, r.category) for r in first] == [("section_0", "home_coffee_tea")]
    assert [(r.rack_id, r.category) for r in second] == [("section_10", "dairy")]
