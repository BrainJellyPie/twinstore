"""Unreadable optional receipt text must not discard valid purchased product lines."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI
from PIL import Image
from pydantic import ValidationError

from store_emulator.domain.config import LLMConfig
from store_emulator.engine import llm_client
from store_emulator.engine.receipt_review import review_receipts
from store_emulator.engine.vision_inputs import _ReceiptVLM, match_lines, vlm_receipt


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("currency", ["USD", "KRW", "JPY"])
@pytest.mark.parametrize("missing", ["store", "date", "time", "currency", "all"])
def test_null_optional_metadata_preserves_lines_currency_review_and_cache(monkeypatch, tmp_path, mode, currency, missing):
    payload = {"store": "Corner shop", "date": "2026-10-24", "time": "10:00", "currency": currency,
               "total": 250, "lines": [{"name": "Tea", "quantity": 2, "unit_price": 125, "line_total": 250}]}
    for field in ["store", "date", "time", "currency"] if missing == "all" else [missing]:
        payload[field] = None
    original = llm_client.litellm.acompletion
    calls = []

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
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/receipt-metadata", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            with Image.new("RGB", (2, 2)) as photo:
                receipt = await vlm_receipt(client, photo, receipt_id="r1", default_currency=currency)
                again = await vlm_receipt(client, photo, receipt_id="r2", default_currency=currency)
            minor = 12500 if currency == "USD" else 125
            assert receipt.currency == currency and receipt.total == 2 * minor
            assert len(receipt.lines) == 1 and receipt.lines[0].quantity == 2
            assert receipt.lines[0].unit_price == minor and receipt.lines[0].line_total == 2 * minor
            assert receipt.store == ("" if missing in {"store", "all"} else "Corner shop")
            assert receipt.timestamp == ("" if missing in {"date", "all"} else "2026-10-24" if missing == "time" else "2026-10-24 10:00")
            assert again.model_copy(update={"receipt_id": "r1"}) == receipt and len(calls) == 1
            review = review_receipts([match_lines(receipt, {"tea": "Tea"})], {"tea": "Tea"}, currency)
            assert review.included_lines == 1 and review.ready == (missing != "time")
            if missing in {"date", "time", "all"}:
                assert any(issue.code == "time_missing" for issue in review.issues)

    asyncio.run(exercise())


@pytest.mark.parametrize("field", ["store", "date", "time", "currency"])
@pytest.mark.parametrize("value", [[], {}, 123])
def test_other_invalid_metadata_types_remain_invalid(field, value):
    with pytest.raises(ValidationError):
        _ReceiptVLM.model_validate({field: value})


@pytest.mark.parametrize("payload", [{"lines": None}, {"lines": [{"name": None}]},
                                     {"lines": [{"name": "Tea", "quantity": None}]}])
def test_required_receipt_structure_is_not_invented(payload):
    with pytest.raises(ValidationError):
        _ReceiptVLM.model_validate(payload)
