"""An omitted grounding list must not be cached as a deliberate empty shelf."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI
from PIL import Image, ImageDraw
from pydantic import Field, create_model

from store_emulator.domain.config import LLMConfig
from store_emulator.engine import llm_client
from store_emulator.engine.capture import detect
from store_emulator.engine.capture.pipeline import capture_shelf


PRODUCTS = [{"box_2d": [x, 30, x + 45, 140]} for x in (30, 120, 210)]


def photo():
    image = Image.new("RGB", (300, 180), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 145, 300, 160), fill="gray")
    for x, color in zip((30, 120, 210), ("red", "green", "blue"), strict=True):
        draw.rectangle((x, 30, x + 45, 140), fill=color)
    return image


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("malformed", [{}, {"boxes": PRODUCTS}])
@pytest.mark.parametrize("recovery", ["corrected", "repeated", "legacy_cache"])
def test_missing_product_list_retries_before_capture_fallback_and_cache(monkeypatch, tmp_path, mode, malformed, recovery):
    original, calls, retry_later = llm_client.litellm.acompletion, [], False

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        corrected = retry_later or recovery == "legacy_cache" or recovery == "corrected" and len(calls) > 1
        answer = {"products": PRODUCTS} if corrected else malformed
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(answer)}}]})

    async def exercise():
        nonlocal retry_later
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/grounding-required-products", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            generate, seeded = client.generate_structured_with_image_async, False

            async def generate_with_old_schema_cache(schema, system, user, image_url, **kwargs):
                nonlocal seeded
                if recovery == "legacy_cache" and not seeded:
                    legacy = create_model("_Grounding", products=(list[detect._GroundedBox], Field(default_factory=list, max_length=80)))
                    messages = client._messages_with_image(system, user, image_url)[0]
                    path = client._cache_path(legacy, messages, kwargs.get("seed"), kwargs.get("max_tokens"))
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(json.dumps({"result": {"products": []}}))
                    seeded = True
                return await generate(schema, system, user, image_url, **kwargs)

            monkeypatch.setattr(client, "generate_structured_with_image_async", generate_with_old_schema_cache)
            detector = detect.VLMGroundingDetector(client, convention="pixels")
            with photo() as image:
                if recovery == "repeated":
                    failed = await capture_shelf(image, detector=detector)
                    assert failed.result.detector == "classic" and failed.result.items
                    assert any("found no products" in note for note in failed.result.notes)
                    assert len(calls) == 2 and not list(tmp_path.rglob("*.json"))
                    retry_later = True
                for repeat in range(2):
                    run = await capture_shelf(image, detector=detector)
                    assert run.result.detector == "vlm" and run.result.detection_sources["vlm"] == 3
                    assert not run.result.notes and len(run.result.items) >= 3
                    assert len(calls) == {"corrected": 2, "repeated": 3, "legacy_cache": 1}[recovery]
                    assert client.get_usage().cached_requests == repeat
                entries = [json.loads(path.read_text())["result"] for path in tmp_path.rglob("*.json")]
                assert sum(entry == {"products": PRODUCTS} for entry in entries) == 1

    asyncio.run(exercise())


@pytest.mark.parametrize("mode", ["json", "json_schema"])
def test_explicit_empty_list_remains_a_valid_cached_detection(monkeypatch, tmp_path, mode):
    original, calls = llm_client.litellm.acompletion, []

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": '{"products": []}'}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/empty-grounding", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            with photo() as image:
                detector = detect.VLMGroundingDetector(client, convention="pixels")
                for repeat in range(2):
                    run = await capture_shelf(image, detector=detector)
                    assert run.result.detector == "classic" and run.result.items
                    assert len(calls) == 1 and client.get_usage().cached_requests == repeat

    asyncio.run(exercise())


def test_grammar_requires_products_but_allows_an_empty_list():
    schema = detect._Grounding.model_json_schema()
    assert "products" in schema.get("required", [])
    assert not schema["properties"]["products"].get("minItems")
    assert detect._Grounding(products=[]).products == []
