"""Finite OCR amounts must validate in their effective currency before being cached."""

import asyncio
import copy
import json

import httpx
import pytest
from instructor.core.exceptions import InstructorRetryException
from openai import AsyncOpenAI
from PIL import Image

from store_emulator.domain.config import LLMConfig
from store_emulator.engine import llm_client
from store_emulator.engine.vision_inputs import vlm_receipt
from tests.engine.test_vision_inputs import _Fake


@pytest.mark.parametrize("field", ["unit_price", "line_total", "total"])
@pytest.mark.parametrize("printed,default,amount", [
    ("USD", "KRW", 90_071_992_547_410.0),
    (" KRW ", "USD", 9_007_199_254_740_992.0),
    ("", "USD", 1e308),
    ("  ", " JPY ", -1e100),
])
@pytest.mark.parametrize("recovers", [False, True])
def test_oversized_receipt_amounts_are_corrected_before_conversion_and_caching(
    tmp_path, monkeypatch, field, printed, default, amount, recovers,
):
    good = {"currency": printed, "total": 200, "lines": [
        {"name": "Tea", "quantity": 2, "unit_price": 100, "line_total": 200}]}
    bad = copy.deepcopy(good)
    (bad if field == "total" else bad["lines"][0])[field] = amount
    requests = []
    original_completion = llm_client.litellm.acompletion

    async def exercise():
        def respond(request):
            requests.append(json.loads(request.content))
            payload = good if recovers and len(requests) > 1 else bad
            return httpx.Response(200, request=request, json={
                "id": "offline-amount", "object": "chat.completion", "created": 0, "model": "local-model",
                "choices": [{"index": 0, "finish_reason": "stop",
                             "message": {"role": "assistant", "content": json.dumps(payload)}}]})

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            transport = AsyncOpenAI(api_key="offline-test", base_url="http://local.invalid/v1",
                                    http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original_completion(**{**kwargs, "client": transport, "api_key": "offline-test", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/local-amount-test", api_base="http://local.invalid/v1",
                structured_output="json_schema", cache_dir=str(tmp_path), seed=0))
            with Image.new("RGB", (2, 2)) as photo:
                if recovers:
                    first = await vlm_receipt(client, photo, receipt_id="r1", default_currency=default)
                    again = await vlm_receipt(client, photo, receipt_id="r1", default_currency=default)
                    assert first == again
                    factor = 100 if first.currency == "USD" else 1
                    assert first.total == 200 * factor and first.lines[0].unit_price == 100 * factor
                    assert client.get_usage().cached_requests == 1
                    saved = [json.loads(path.read_text())["result"] for path in tmp_path.rglob("*.json")]
                    assert len(saved) == 1 and saved[0]["total"] == 200
                else:
                    with pytest.raises(InstructorRetryException):
                        await vlm_receipt(client, photo, receipt_id="r1", default_currency=default)
                    assert not list(tmp_path.rglob("*.json"))

    asyncio.run(exercise())
    assert len(requests) == 2


@pytest.mark.parametrize("printed,default", [("KRW", "USD"), ("", "KRW"), (" ", " JPY ")])
@pytest.mark.parametrize("sign", [-1, 1])
def test_large_supported_zero_decimal_amounts_remain_reviewable(printed, default, sign):
    amount = sign * 9_007_199_254_740_991
    model = _Fake({"currency": printed, "total": amount, "lines": [
        {"name": "Amount", "unit_price": amount, "line_total": amount}]})
    with Image.new("RGB", (2, 2)) as photo:
        receipt = asyncio.run(vlm_receipt(model, photo, receipt_id="boundary", default_currency=default))
    assert receipt.total == receipt.lines[0].unit_price == receipt.lines[0].line_total == amount


def test_simultaneous_receipts_keep_their_own_default_currency():
    class Model:
        async def generate_structured_with_image_async(self, schema, *args, **kwargs):
            await asyncio.sleep(0)
            return schema.model_validate({"currency": "", "total": 9_007_199_254_740_991})

    async def read():
        with Image.new("RGB", (2, 2)) as photo:
            return await asyncio.gather(
                vlm_receipt(Model(), photo, receipt_id="krw", default_currency="KRW"),
                vlm_receipt(Model(), photo, receipt_id="usd", default_currency="USD"),
                return_exceptions=True,
            )

    krw, usd = asyncio.run(read())
    assert krw.total == 9_007_199_254_740_991 and krw.currency == "KRW"
    assert isinstance(usd, ValueError)
