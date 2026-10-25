"""A grammar-limited pack target may identify only one full catalog name."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI
from PIL import Image

from store_emulator.domain.config import LLMConfig
from store_emulator.engine import llm_client
from store_emulator.engine.package_reader import read_pack


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("word", ["Tea", "녹차"])
@pytest.mark.parametrize("case", ["unique", "exact_limit", "long_collision", "short_collision", "short_prefix", "unknown", "duplicate"])
def test_bounded_pack_names_preserve_unique_identity_through_http_and_cache(monkeypatch, tmp_path, mode, word, case):
    prefix = (word * 120)[:120]
    full = prefix + " 500 ml"
    products = [full]
    asked, expected = prefix, full
    if case == "exact_limit":
        products, expected = [prefix], prefix
    elif case == "long_collision":
        products.append(prefix + " 1 L")
        expected = ""
    elif case == "short_collision":
        products.append(prefix)
        expected = ""
    elif case == "short_prefix":
        asked, expected = prefix[:-1], ""
    elif case == "unknown":
        asked, expected = "Unknown product", ""
    elif case == "duplicate":
        products.append(full)
    payload = {"printed_text": "Leafy Tea 500 ml " + full, "name": "Tea 500 ml", "brand": "Leafy", "shelf_product": asked, "confidence": .9}
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
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/pack-bounded", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            with Image.new("RGB", (2, 2)) as photo:
                result = await read_pack(client, photo, products)
                assert result.shelf_product == expected
                assert result.name == "Tea 500 ml" and result.brand == "Leafy" and result.confidence == .9
                assert (await read_pack(client, photo, products)).model_dump() == result.model_dump()
            assert len(calls) == 2 and client.get_usage().cached_requests == 2
            if mode == "json_schema":
                schema = calls[1]["response_format"]["json_schema"]["schema"]
                assert schema["properties"]["shelf_product"]["maxLength"] == 120

    asyncio.run(exercise())
