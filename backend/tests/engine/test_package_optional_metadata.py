"""Partial pack readings normalize only unknown text, before caching and linking."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI
from PIL import Image
from pydantic import ValidationError

from store_emulator.domain.config import LLMConfig
from store_emulator.engine import llm_client
from store_emulator.engine.package_reader import PackReading, read_pack


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("missing", ["name", "brand", "size", "category", "shelf_product", "all"])
def test_partial_text_reads_through_http_and_reuses_the_normalized_cache(monkeypatch, tmp_path, mode, missing):
    payload = dict(printed_text="Leafy Tea 500 ml", name=" Tea 500 ml ", brand=" Leafy ", size=" 500 ml ", category=" Tea ", shelf_product=" TEA 500 ML ", confidence=.8)
    fields = ["name", "brand", "size", "category", "shelf_product"] if missing == "all" else [missing]
    for field in fields:
        payload[field] = None
    original, calls = llm_client.litellm.acompletion, []

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(payload)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/pack-metadata", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            with Image.new("RGB", (2, 2)) as photo:
                result = await read_pack(client, photo, ["Tea 500 ml"])
                cached = await read_pack(client, photo, ["Tea 500 ml"])
                assert cached.model_dump() == result.model_dump()
            expected = {key: "" if value is None else value.strip() if isinstance(value, str) else value for key, value in payload.items()
                        if key != "printed_text"}
            if "shelf_product" not in fields:
                expected["shelf_product"] = "Tea 500 ml"
            assert result.model_dump() == expected and len(calls) == 2
            saved = [json.loads(path.read_text())["result"] for path in tmp_path.glob("*/*.json")]
            assert all(any(record.get(field) == "" for record in saved) for field in fields)

    asyncio.run(exercise())


@pytest.mark.parametrize("field", ["name", "brand", "size", "category", "shelf_product"])
@pytest.mark.parametrize("value", [[], {}, 123])
def test_non_null_wrong_text_types_remain_invalid(field, value):
    with pytest.raises(ValidationError):
        PackReading.model_validate({field: value})


@pytest.mark.parametrize("value", [None, float("nan"), -1, 2])
def test_confidence_is_not_invented_or_relaxed(value):
    with pytest.raises(ValidationError):
        PackReading.model_validate({"confidence": value})
