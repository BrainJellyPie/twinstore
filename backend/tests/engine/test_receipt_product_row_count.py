"""Declared receipt rows must match the actual list before a reply can be cached."""

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


@pytest.mark.parametrize("count", [0, 2, -1, 1.5, True, False, "two"])
def test_inconsistent_or_invalid_product_counts_are_rejected(count):
    with pytest.raises(ValidationError):
        _ReceiptVLM.model_validate({"product_row_count": count, "lines": [{"name": "Tea"}]})


@pytest.mark.parametrize("count", [None, 1])
@pytest.mark.parametrize("line", [
    {"name": "", "quantity": 2, "unit_price": None, "line_total": None},
    {"name": "Tea", "quantity": 1, "unit_price": 0, "line_total": 0},
    {"name": "Apples", "quantity": -0.5, "unit_price": 4, "line_total": -2},
])
def test_counts_preserve_unreadable_free_and_returned_rows(count, line):
    reading = _ReceiptVLM.model_validate({"product_row_count": count, "lines": [line]})
    assert reading.lines[0].model_dump() == line


def test_legacy_partial_receipts_and_empty_transactions_remain_readable():
    assert _ReceiptVLM.model_validate({"lines": [{"name": "Tea"}]}).product_row_count is None
    assert _ReceiptVLM.model_validate({"product_row_count": 0, "lines": []}).lines == []
    rows = [{"name": f"Product {i}"} for i in range(600)]
    assert len(_ReceiptVLM.model_validate({"product_row_count": 600, "lines": rows}).lines) == 600


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("recovers", [False, True])
def test_count_mismatches_retry_before_caching(tmp_path, monkeypatch, mode, recovers):
    first_line = {"name": "Tea", "quantity": 2, "unit_price": 2.5, "line_total": 5}
    second_line = {"name": "Water", "quantity": 1, "unit_price": 1, "line_total": 1}
    bad = {"product_row_count": 2, "lines": [first_line], "currency": "USD", "total": 6}
    good = {**bad, "lines": [first_line, second_line]}
    requests = []
    original_completion = llm_client.litellm.acompletion

    async def exercise():
        def respond(request):
            requests.append(json.loads(request.content))
            payload = good if recovers and len(requests) > 1 else bad
            return httpx.Response(200, request=request, json={
                "id": "offline-count", "object": "chat.completion", "created": 0, "model": "local-model",
                "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": json.dumps(payload)}}]})

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            transport = AsyncOpenAI(api_key="offline-test", base_url="http://local.invalid/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original_completion(**{**kwargs, "client": transport, "api_key": "offline-test", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/local-receipt-count", api_base="http://local.invalid/v1",
                structured_output=mode, cache_dir=str(tmp_path), seed=0))
            with Image.new("RGB", (2, 2)) as image:
                if not recovers:
                    with pytest.raises(InstructorRetryException):
                        await vlm_receipt(client, image, receipt_id="r1")
                    assert not list(tmp_path.rglob("*.json"))
                    return
                first = await vlm_receipt(client, image, receipt_id="r1")
                cached = await vlm_receipt(client, image, receipt_id="r2")
                assert len(first.lines) == len(cached.lines) == 2
                assert first.lines[0].line_total == cached.lines[0].line_total == 500
                assert client.get_usage().cached_requests == 1
                saved = [json.loads(path.read_text())["result"] for path in tmp_path.rglob("*.json")]
                assert len(saved) == 1 and saved[0]["product_row_count"] == len(saved[0]["lines"]) == 2

    asyncio.run(exercise())
    assert len(requests) == 2
