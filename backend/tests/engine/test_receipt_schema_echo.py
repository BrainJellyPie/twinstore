"""A copied JSON Schema is not an empty receipt and must never enter its cache."""

import asyncio
import json

import httpx
import pytest
from instructor.core.exceptions import InstructorRetryException
from openai import AsyncOpenAI
from PIL import Image
from pydantic import ValidationError

from store_emulator.domain.config import LLMConfig
from store_emulator.engine import llm_client
from store_emulator.engine.vision_inputs import _ReceiptVLM, vlm_receipt


@pytest.mark.parametrize("payload", [
    _ReceiptVLM.model_json_schema(),
    {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object"},
    {"$defs": {"Row": {"type": "object"}}},
    {"properties": {"lines": {"type": "array"}}},
    {"required": ["store", "lines"], "type": "object"},
])
def test_schema_only_replies_are_not_valid_empty_receipts(payload):
    with pytest.raises(ValidationError, match="JSON Schema"):
        _ReceiptVLM.model_validate(payload)


def test_schema_annotations_do_not_remove_real_or_legacy_receipt_values():
    reading = _ReceiptVLM.model_validate({"store": "", "total": 0, "product_row_count": 1,
        "lines": [{"name": "Tea", "quantity": 1, "unit_price": 0, "line_total": 0}],
        "properties": {"unused": {"type": "string"}}, "$defs": {}, "required": ["lines"]})
    assert reading.total == 0 and reading.lines[0].name == "Tea"
    assert "properties" not in reading.model_dump() and "$defs" not in reading.model_dump()
    assert _ReceiptVLM.model_validate({"store": None, "properties": {}}).store == ""
    assert _ReceiptVLM.model_validate({}).lines == []


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("recovers", [False, True])
def test_schema_echo_retries_instead_of_caching_a_blank_receipt(tmp_path, monkeypatch, mode, recovers):
    echo = _ReceiptVLM.model_json_schema()
    good = {"store": "Corner", "date": "2026-10-27", "time": "14:05", "currency": "USD",
        "product_row_count": 1, "lines": [{"name": "Tea", "quantity": 1, "unit_price": 0, "line_total": 0}],
        "total_row": "TOTAL 0.00", "total": 0}
    requests = []
    original_completion = llm_client.litellm.acompletion

    async def exercise():
        def respond(request):
            requests.append(json.loads(request.content))
            payload = good if recovers and len(requests) > 1 else echo
            return httpx.Response(200, request=request, json={
                "id": "offline-echo", "object": "chat.completion", "created": 0, "model": "local-model",
                "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": json.dumps(payload)}}]})

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            transport = AsyncOpenAI(api_key="offline-test", base_url="http://local.invalid/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original_completion(**{**kwargs, "client": transport, "api_key": "offline-test", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/local-receipt-echo", api_base="http://local.invalid/v1",
                structured_output=mode, cache_dir=str(tmp_path), seed=0))
            with Image.new("RGB", (2, 2)) as image:
                if not recovers:
                    with pytest.raises(InstructorRetryException):
                        await vlm_receipt(client, image, receipt_id="r1")
                    assert not list(tmp_path.rglob("*.json"))
                    return
                first = await vlm_receipt(client, image, receipt_id="r1")
                cached = await vlm_receipt(client, image, receipt_id="r2")
                assert first.lines[0].name == cached.lines[0].name == "Tea"
                assert first.total == cached.total == 0
                assert client.get_usage().cached_requests == 1
                saved = [json.loads(path.read_text())["result"] for path in tmp_path.rglob("*.json")]
                assert len(saved) == 1 and saved[0]["lines"][0]["name"] == "Tea"

    asyncio.run(exercise())
    assert len(requests) == 2
