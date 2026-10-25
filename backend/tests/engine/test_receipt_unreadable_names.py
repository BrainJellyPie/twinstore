"""A purchased line with an unreadable name must survive OCR and block unreviewed sales export."""

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
from store_emulator.engine.vision_inputs import match_lines, vlm_receipt


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("currency", ["USD", "KRW"])
@pytest.mark.parametrize("blank", ["", " \t\u3000"])
@pytest.mark.parametrize("quantity,unit,total", [(2, 3, 5), (0.5, 2, 1), (1, 0, 0), (1, None, None)])
def test_http_unreadable_names_keep_their_amounts_until_review(monkeypatch, tmp_path, mode, currency, blank, quantity, unit, total):
    payload = {"date": "2026-10-25", "time": "12:00", "currency": currency, "lines": [
        {"name": "Tea", "quantity": 1, "line_total": 2},
        {"name": blank, "quantity": quantity, "unit_price": unit, "line_total": total},
        {"name": "Water", "quantity": 1, "line_total": 1},
    ]}
    products = {"tea": "Tea", "water": "Water", "milk": "Milk"}
    scale = 100 if currency == "USD" else 1
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
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/unreadable-receipt-name",
                api_base="http://127.0.0.1:8081/v1", structured_output=mode, cache_dir=str(tmp_path)))
            with Image.new("RGB", (2, 2)) as photo:
                for repeat in range(2):
                    reading = await vlm_receipt(client, photo, receipt_id="receipt", default_currency=currency)
                    assert [line.name for line in reading.lines] == ["Tea", "", "Water"]
                    missing = reading.lines[1]
                    assert missing.quantity == quantity
                    assert missing.unit_price == (None if unit is None else unit * scale)
                    assert missing.line_total == (None if total is None else total * scale)
                    matched = match_lines(reading, products)
                    assert [line.sku for line in matched.lines] == ["tea", "", "water"]
                    before = matched.model_dump()
                    blocked = review_receipts([matched], products, currency)
                    assert not blocked.ready and not blocked.csv and blocked.included_lines == 3
                    assert any(issue.code == "sku" and issue.line_index == 1 for issue in blocked.issues)
                    assert matched.model_dump() == before
                    corrected = matched.model_copy(deep=True)
                    corrected.lines[1].sku = "milk"
                    if total is None:
                        corrected.lines[1].line_total = 7 * scale
                    approved = review_receipts([corrected], products, currency)
                    assert approved.ready and approved.included_lines == 3
                    rows = parse_pos_csv(approved.csv.encode())
                    assert [row.sku for row in rows] == ["tea", "milk", "water"]
                    assert rows[1].quantity == quantity
                    assert rows[1].quantity * rows[1].unit_price == (7 if total is None else total) * scale
                    excluded = matched.model_copy(deep=True)
                    excluded.lines.pop(1)
                    assert review_receipts([excluded], products, currency).ready
                    assert len(calls) == 1 and client.get_usage().cached_requests == repeat

    asyncio.run(exercise())
