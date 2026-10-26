"""Unrelated early catalog entries must not hide observed products near the end."""
import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI
from PIL import Image

from store_emulator.domain.config import LLMConfig
from store_emulator.engine import llm_client
from store_emulator.engine.package_reader import MAX_LISTED, read_pack


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("position", [0, 149, 150, 4999])
def test_observed_product_is_found_at_catalog_boundaries_and_cached(monkeypatch, tmp_path, mode, position):
    name = "Leafy Green Tea 500 ml"
    unrelated = [f"Unrelated product {i:04d}" for i in range(position)]
    products = [*unrelated, name, "Leafy Green Tea 1 L", "Leafy Black Tea 500 ml"]
    original, calls = llm_client.litellm.acompletion, []

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        user = next(m["content"] for m in body["messages"] if m["role"] == "user")
        if isinstance(user, list):
            assert "Unrelated product" not in json.dumps(body)
            payload = {"printed_text": "LEAFY GREEN TEA 500 ml", "name": "Green Tea", "brand": "Leafy",
                       "size": "500 ml", "category": "Tea", "confidence": 1}
        else:
            context = json.loads(user)
            assert context["store_products"] == [name]
            payload = {"shelf_product": name}
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop", "message": {
                "role": "assistant", "content": json.dumps(payload)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/large-pack-catalog", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            with Image.new("RGB", (2, 2)) as photo:
                reading = await read_pack(client, photo, products)
                assert reading.shelf_product == name and len(calls) == 2
                assert await read_pack(client, photo, products) == reading and len(calls) == 2
                assert await read_pack(client, photo, [name, *products]) == reading and len(calls) == 2
                absent = await read_pack(client, photo, [*unrelated, *products[-2:]])
                assert absent.shelf_product == "" and len(calls) == 2

    asyncio.run(exercise())


def test_matching_task_remains_bounded_after_evidence_filtering():
    captured = []

    class Model:
        async def generate_structured_with_image_async(self, schema, *args, **kwargs):
            return schema(printed_text="Tea", name="Tea", confidence=1)

        async def generate_structured_async(self, schema, system, user, **kwargs):
            captured.append(json.loads(user)["store_products"])
            return schema(shelf_product="")

    observed_variants = ["Tea" + " " * i for i in range(MAX_LISTED + 1)]
    catalog = [f"Unrelated {i}" for i in range(MAX_LISTED)] + observed_variants
    with Image.new("RGB", (2, 2)) as photo:
        result = asyncio.run(read_pack(Model(), photo, catalog))
    assert result.shelf_product == "" and captured == [observed_variants[:MAX_LISTED]]
