"""Catalog candidates must never become image evidence or authorize an unsupported package link."""

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
@pytest.mark.parametrize("case", ["label", "fullwidth", "empty", "null", "whitespace", "wrong_variants", "partial_word", "no_catalog", "invented_metadata", "percentage", "malicious_match"])
def test_only_observed_label_text_can_reach_product_matching(monkeypatch, tmp_path, mode, case):
    name = "Leafy Green Tea 500 ml"
    products = [name, "Leafy Green Tea 1 L", "Leafy Black Tea 500 ml"]
    printed = "LEAFY GREEN TEA 500ml"
    if case == "fullwidth": printed = "ＬＥＡＦＹ　ＧＲＥＥＮ　ＴＥＡ　５００ｍｌ"
    elif case == "empty": printed = ""
    elif case == "null": printed = None
    elif case == "whitespace": printed = "  \t\n"
    elif case == "wrong_variants": products = products[1:]
    elif case == "partial_word": printed, products = "ICECREAM 500 ml", ["Cream 500 ml"]
    elif case == "no_catalog": products = []
    matched = case in {"label", "fullwidth", "invented_metadata", "percentage", "malicious_match"}
    original, calls = llm_client.litellm.acompletion, []
    observations = 0

    def respond(request):
        nonlocal observations
        body = json.loads(request.content)
        calls.append(body)
        user = next(message["content"] for message in body["messages"] if message["role"] == "user")
        if isinstance(user, list):
            observations += 1
            assert all(product not in json.dumps(body) for product in products)
            if mode == "json_schema":
                schema = body["response_format"]["json_schema"]["schema"]
                assert next(iter(schema["properties"])) == "printed_text"
                assert set(schema["required"]) == {"printed_text", "name", "brand", "size", "category", "confidence"}
                assert schema["properties"]["confidence"]["enum"] == [0, .25, .5, .75, 1]
            payload = {"printed_text": printed, "name": "Green Tea", "brand": "Invented" if case == "invented_metadata" else "Leafy",
                       "size": "100g" if case == "invented_metadata" else "500 ml", "category": "Tea",
                       "confidence": 100 if case == "percentage" and observations == 1 else .75}
        else:
            assert matched, "Unlabelled/unsupported products must not trigger matching at all"
            context = json.loads(user)
            assert context["store_products"] == [name]
            assert context["observation"]["printed_text"] == printed
            payload = {"shelf_product": "Leafy Green Tea 1 L" if case == "malicious_match" else name}
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(payload)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/package-evidence", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            with Image.new("RGB", (2, 2)) as photo:
                result = await read_pack(client, photo, products)
                assert result.shelf_product == (name if matched and case != "malicious_match" else "") and result.confidence == .75
                if case in {"empty", "null", "whitespace", "invented_metadata"}:
                    assert result.brand == result.size == ""
                expected_calls = 1 + matched + (case == "percentage")
                assert len(calls) == expected_calls
                assert (await read_pack(client, photo, products)).model_dump() == result.model_dump()
                assert len(calls) == expected_calls
                if matched:
                    # Reuse the image observation in another catalog, never its previous product link.
                    changed = await read_pack(client, photo, ["Leafy Green Tea 1 L", "Leafy Black Tea 500 ml"])
                    assert changed.shelf_product == "" and len(calls) == expected_calls

    asyncio.run(exercise())
