"""A similar OCR name must not silently assign revenue to another product."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI
from PIL import Image

from store_emulator.application.pos import parse_pos_csv
from store_emulator.domain.config import LLMConfig
from store_emulator.engine import llm_client
from store_emulator.engine.receipt_review import review_receipts
from store_emulator.engine.vision_inputs import match_lines, receipts_csv, vlm_receipt
from tests.engine.test_rival_similar_products import DIFFERENT


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("currency", ["USD", "KRW"])
@pytest.mark.parametrize("ours,theirs", DIFFERENT)
def test_http_variant_requires_review_before_sales_export(monkeypatch, tmp_path, mode, currency, ours, theirs):
    products = {"ours": ours, "tea": "Tea", "reviewed": "Hand reviewed product"}
    payload = {"date": "2026-10-25", "time": "12:00", "currency": currency, "total": 5, "lines": [
        {"name": theirs, "quantity": 0.5, "line_total": 4},
        {"name": "TEA", "quantity": 1, "line_total": 1},
    ]}
    scale = 100 if currency == "USD" else 1
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
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/receipt-similar-products",
                api_base="http://127.0.0.1:8081/v1", structured_output=mode, cache_dir=str(tmp_path)))
            with Image.new("RGB", (2, 2)) as photo:
                for repeat in range(2):
                    reading = await vlm_receipt(client, photo, receipt_id="receipt", default_currency=currency)
                    before = reading.model_dump()
                    matched = match_lines(reading, products)
                    assert [line.sku for line in matched.lines] == ["", "tea"]
                    assert matched.lines[0].name == theirs and matched.lines[0].line_total == 4 * scale
                    assert [row.sku for row in parse_pos_csv(receipts_csv([matched]).encode())] == ["tea"]
                    review = review_receipts([matched], products, currency)
                    assert not review.ready and not review.csv and review.included_lines == 2
                    assert any(issue.code == "sku" and issue.line_index == 0 for issue in review.issues)
                    corrected = matched.model_copy(deep=True)
                    corrected.lines[0].sku = "reviewed"
                    approved = review_receipts([corrected], products, currency)
                    assert approved.ready
                    rows = parse_pos_csv(approved.csv.encode())
                    assert [row.sku for row in rows] == ["reviewed", "tea"]
                    assert rows[0].quantity == 0.5 and rows[0].quantity * rows[0].unit_price == 4 * scale
                    assert sum(row.quantity * row.unit_price for row in rows) == 5 * scale
                    assert reading.model_dump() == before and not matched.lines[0].matched
                    assert len(calls) == 1 and client.get_usage().cached_requests == repeat

    asyncio.run(exercise())
