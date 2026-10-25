"""Foreign shelf-tag amounts must not become exact prices in the store's currency."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI
from PIL import Image

from store_emulator.domain.capture import ShelfItemLabel
from store_emulator.domain.config import LLMConfig
from store_emulator.engine import llm_client
from store_emulator.engine.capture.catalog_match import price_minor_units, typical_price
from store_emulator.engine.capture.detect import Detection
from store_emulator.engine.capture.frame import make_frame
from store_emulator.engine.capture.pipeline import build_items
from store_emulator.engine.capture.recognize import FacingGroup, VLMLabeler, describe
from store_emulator.engine.prompting import display_price


CONFLICTS = [
    ("$2.49", "KRW"), ("₩1,800", "USD"), ("1,800원", "USD"), ("1800 KRW", "USD"),
    ("249 USD", "KRW"), ("12,50 €", "USD"), ("JPY 300", "KRW"), ("¥300", "USD"),
    ("300円", "CNY"), ("￥３００", "KRW"), ("＄２．４９", "JPY"), ("£2.49", "EUR"),
    ("2.49 usd", "EUR"), ("２．４９ ＥＵＲ", "USD"), ("CAD $2.49", "USD"),
    ("CNY ¥300", "JPY"), ("USD 2.49 EUR", "USD"), ("$2.49 KRW", "KRW"),
    ("249 EUR cents", "USD"), ("₩", "USD"), ("USD", "KRW"),
]


@pytest.mark.parametrize("printed,currency", CONFLICTS)
@pytest.mark.parametrize("guess", [None, 2.49, 1800])
def test_conflicting_currency_is_unreadable_even_with_a_numeric_model_guess(printed, currency, guess):
    assert price_minor_units(ShelfItemLabel(price_text=printed, price=guess), currency.lower(), 249) is None


@pytest.mark.parametrize("printed,currency,expected", [
    ("$2.49", "CAD", 249), ("$2.49", "AUD", 249), ("$300", "TWD", 300),
    ("¥300", "CNY", 30000), ("¥300", "JPY", 300), ("300円", "JPY", 300),
    ("CAD $2.49", "CAD", 249), ("CHF 2.49", "CHF", 249), ("1,800원", "KRW", 1800),
    ("USD 249 cents", "USD", 249), ("249 cents", "EUR", 249), ("$2.49 OFF", "USD", 249),
    ("25 lei", "RON", 2500), ("2.49", "USD", 249), ("", "USD", 249),
])
def test_matching_shared_or_unmarked_units_keep_existing_price_semantics(printed, currency, expected):
    assert price_minor_units(ShelfItemLabel(price_text=printed, price=2.49), currency, None) == expected


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("printed,currency", CONFLICTS[:8])
def test_http_capture_and_cached_labels_keep_products_and_flag_foreign_prices(monkeypatch, tmp_path, mode, printed, currency):
    answer = dict(name="Cola 500ml", category="soft drink", price_text=printed, price=2.49, confidence=9)
    original, calls = llm_client.litellm.acompletion, []

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(answer)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/capture-price-currency", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            with Image.new("RGB", (100, 80), "white") as photo:
                frame = make_frame(photo)
                labeler = VLMLabeler(client, currency=currency)
                for repeat in range(2):
                    labels = [await labeler.label(photo), ShelfItemLabel(name="Mineral Water 500ml", category="water",
                        price_text=display_price(125, currency))]
                    groups = []
                    for index, label in enumerate(labels):
                        detection = Detection(x1=index * 50, y1=0, x2=index * 50 + 40, y2=60, band=0)
                        groups.append(FacingGroup(band=0, facings=[detection], descriptor=describe(photo, detection), label=label))
                    items, _ = build_items(frame, groups, [3], currency=currency, rack_type="shelf")
                    assert len(items) == 2 and all(item.labeled for item in items)
                    assert items[0].name == "Cola 500ml" and items[0].price_text == printed
                    assert items[0].price_estimated
                    assert items[0].price == typical_price("soft_drinks", "Cola 500ml", currency)[0]
                    assert items[1].price == 125 and not items[1].price_estimated
                    assert len(calls) == 1 and client.get_usage().cached_requests == repeat

    asyncio.run(exercise())
