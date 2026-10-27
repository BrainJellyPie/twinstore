"""An explicitly transcribed subtotal cannot establish the receipt's final total."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI
from PIL import Image

from store_emulator.domain.config import LLMConfig
from store_emulator.engine import llm_client
from store_emulator.engine.receipt_review import review_receipts
from store_emulator.engine.vision_inputs import match_lines, vlm_receipt


SUBTOTALS = ["SUBTOTAL 6.00", "Subtotal: $6.00", "SUBTOTAL6.00", "Sub-total 6.00",
    "SUB TOTAL 6.00", "ＳＵＢＴＯＴＡＬ ６．００", "Sous-total 6,00 €",
    "소계 6", "소계금액 6", "小計6", "小计 6"]


class Reading:
    def __init__(self, row):
        self.row = row

    async def generate_structured_with_image_async(self, model, *_args, **_kwargs):
        return model.model_validate({"date": "2026-10-27", "time": "14:05", "total_row": self.row, "total": 6,
            "lines": [{"name": "Tea", "quantity": 0.5, "unit_price": 4, "line_total": 2}]})


@pytest.mark.parametrize("currency", ["USD", "KRW", "JPY"])
@pytest.mark.parametrize("row", SUBTOTALS)
def test_subtotal_evidence_leaves_total_unknown_and_keeps_purchased_amounts(currency, row):
    with Image.new("RGB", (2, 2)) as photo:
        reading = asyncio.run(vlm_receipt(Reading(row), photo, receipt_id="receipt", default_currency=currency))
    scale = 100 if currency == "USD" else 1
    assert reading.total is None and reading.notes == [row]
    assert reading.timestamp == "2026-10-27 14:05" and reading.currency == currency
    assert reading.lines[0].quantity == 0.5
    assert reading.lines[0].unit_price == 4 * scale and reading.lines[0].line_total == 2 * scale
    review = review_receipts([match_lines(reading, {"tea": "Tea"})], {"tea": "Tea"}, currency)
    assert review.ready and review.included_lines == 1
    assert review.receipts[0].total is None and review.receipts[0].notes == [row]


@pytest.mark.parametrize("row", ["", None, "TOTAL 6.00", "Grand total 6.00", "TOTAL (incl. VAT) 6.00",
    "TOTAL 6.00 (SUBTOTAL 5.00)", "Amount due 6.00", "합계 6", "合計6", "合计6", "Final total 6.00", "Subtotalled items 6.00"])
def test_other_or_absent_evidence_is_not_reclassified_as_a_subtotal(row):
    with Image.new("RGB", (2, 2)) as photo:
        reading = asyncio.run(vlm_receipt(Reading(row), photo, receipt_id="receipt"))
    assert reading.total == 600 and reading.notes == []


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("row,total", [("SUBTOTAL 6.00", None), ("TOTAL 6.00", 600)])
def test_http_reading_and_cached_reuse_keep_the_printed_row_evidence(monkeypatch, tmp_path, mode, row, total):
    payload = {"store": "Corner", "date": "2026-10-27", "time": "14:05", "currency": "USD",
        "lines": [{"name": "Tea", "quantity": 2, "unit_price": 2.5, "line_total": 5}],
        "total_row": row, "total": 6}
    original, calls = llm_client.litellm.acompletion, []

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        if mode == "json_schema":
            schema = body["response_format"]["json_schema"]["schema"]
            assert "total_row" in schema["required"]
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(payload)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/receipt-source-row", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            with Image.new("RGB", (2, 2)) as photo:
                for repeat in range(2):
                    reading = await vlm_receipt(client, photo, receipt_id=f"r{repeat}")
                    assert reading.total == total
                    assert reading.notes == ([row] if total is None else [])
                    assert reading.lines[0].quantity == 2 and reading.lines[0].line_total == 500
                    assert len(calls) == 1 and client.get_usage().cached_requests == repeat

    asyncio.run(exercise())
