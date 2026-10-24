"""A readable receipt's item list must not be lost to the storefront-sized output cap."""

import asyncio
import csv
import io
import json

import httpx
import pytest
from openai import AsyncOpenAI
from PIL import Image

from store_emulator.application import vision_inputs as app_inputs
from store_emulator.application.storage.io import write_json
from store_emulator.application.storage.setups import metadata_path
from store_emulator.domain.config import LLMConfig, SimulationConfig
from store_emulator.engine import llm_client
from store_emulator.engine.vision_inputs import vlm_appeal


# Compact / indented JSON measured with the existing Qwen3.5 tokenizer.
TOKENS = {(5, "USD"): (181, 313), (5, "KRW"): (182, 314),
          (30, "USD"): (881, 1538), (30, "KRW"): (883, 1540),
          (60, "USD"): (1721, 3008), (60, "KRW"): (1723, 3010)}


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("count", [5, 30, 60])
@pytest.mark.parametrize("currency", ["USD", "KRW"])
@pytest.mark.parametrize("pretty", [False, True])
def test_receipt_lines_survive_reading_matching_review_export_and_cache(monkeypatch, tmp_path, mode, count, currency, pretty):
    monkeypatch.chdir(tmp_path)
    pid = "proj_receiptbudget"
    write_json(metadata_path(pid), {"currency": currency})
    price, name, minor = (1.25, "Tea", 125) if currency == "USD" else (1500, "녹차", 1500)
    payload = {"store": "Corner Shop", "date": "2026-10-24", "time": "12:00", "currency": currency,
               "lines": [{"name": f"{name} {i + 1:02d}", "quantity": 1, "unit_price": price, "line_total": price}
                         for i in range(count)], "total": price * count}
    content = json.dumps(payload, ensure_ascii=False, indent=2) if pretty else json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    required = TOKENS[count, currency][int(pretty)]
    products = {f"sku_{i}": line["name"] for i, line in enumerate(payload["lines"])}
    monkeypatch.setattr(app_inputs, "_receipt_target", lambda *args: (products, currency))
    config = LLMConfig(model="openai/local-receipt", api_base="http://127.0.0.1:8081/v1", max_tokens=320,
                       structured_output=mode, cache_dir=str(tmp_path / "cache"), seed=0)
    monkeypatch.setattr(app_inputs, "capture_llm_config", lambda *args: config)
    original, requests = llm_client.litellm.acompletion, []

    def respond(request):
        body = json.loads(request.content)
        requests.append(body)
        receipt = "transcribe shop receipts" in body["messages"][0]["content"]
        truncated = receipt and body["max_tokens"] < required
        answer = (content[:32] if truncated else content) if receipt else json.dumps({
            "signage": 5, "entrance": 5, "window": 5, "upkeep": 5, "overall": 5})
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "length" if truncated else "stop",
                "message": {"role": "assistant", "content": answer}}]})

    async def completion(**kwargs):
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)
            return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

    monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
    with Image.new("RGB", (400, 800), "white") as photo:
        buffer = io.BytesIO()
        photo.save(buffer, format="PNG")

        def read():
            return app_inputs.read_receipts(pid, [buffer.getvalue()], setup_id=None, model="local", config=SimulationConfig())

        result = read()
        assert result.matched_lines == count and result.unmatched_lines == 0
        receipt = result.receipts[0]
        assert len(receipt.lines) == count and not receipt.notes
        assert receipt.total == minor * count and receipt.currency == currency
        assert all(line.quantity == 1 and line.unit_price == line.line_total == minor for line in receipt.lines)
        review = app_inputs.review_receipt_batch(pid, result.receipts, setup_id=None, run_id=None, config=SimulationConfig())
        assert review.ready
        rows = list(csv.DictReader(io.StringIO(result.csv)))
        assert len(rows) == count and {row["sku"] for row in rows} == set(products)
        assert all(float(row["unit_price"]) == minor and float(row["line_total"]) == minor for row in rows)
        assert read() == result and len(requests) == 1
        assert required <= requests[0]["max_tokens"] <= 6144
        client = app_inputs._client(SimulationConfig(), "local")
        assert client is not None and client.max_tokens == 1500
        assert asyncio.run(vlm_appeal(client, photo)).overall == 5
    assert len(requests) == 2 and requests[-1]["max_tokens"] == 1500
    assert config.max_tokens == 320
