"""A finite but unrepresentable model price cannot overwrite a usable shelf price."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI
from PIL import Image

from store_emulator.domain.capture import CaptureResult, ShelfItemLabel
from store_emulator.domain.config import LLMConfig
from store_emulator.domain.product_edits import MAX_PRICE
from store_emulator.engine import llm_client
from store_emulator.engine.capture.catalog_match import price_minor_units, typical_price
from store_emulator.engine.capture.detect import Detection
from store_emulator.engine.capture.frame import make_frame
from store_emulator.engine.capture.pipeline import build_items
from store_emulator.engine.capture.planogram import replace_rack_face
from store_emulator.engine.capture.recognize import FacingGroup, VLMLabeler, describe
from store_emulator.engine.prompting import display_price
from tests.engine.test_scenario_target_matching import target_store


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("currency", ["USD", "KRW"])
@pytest.mark.parametrize("fault", ["finite_guess", "long_tag", "just_above_limit"])
@pytest.mark.parametrize("known", [False, True])
def test_http_unsafe_prices_preserve_products_and_apply_safe_estimates(monkeypatch, tmp_path, mode, currency, fault, known):
    store = target_store()
    if not known:
        store.racks[0].slots = []
    before = store.model_dump_json()
    printed = "999999999999999999999" if fault == "long_tag" else (
        f"{MAX_PRICE + 1}{'¢' if currency == 'USD' else '원'}" if fault == "just_above_limit" else "")
    answer = dict(name="Cola 500ml", category="soft drink", price_text=printed,
                  price=1e306 if fault == "finite_guess" else 2.49, confidence=9)
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
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/capture-safe-prices", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            with Image.new("RGB", (100, 80), "white") as photo:
                labeler = VLMLabeler(client, currency=currency)
                for repeat in range(2):
                    labels = [await labeler.label(photo), ShelfItemLabel(name="Mineral Water 500ml", category="water",
                        price_text=display_price(125, currency))]
                    groups = []
                    for index, label in enumerate(labels):
                        box = Detection(x1=index * 50, y1=0, x2=index * 50 + 40, y2=60, band=0)
                        groups.append(FacingGroup(band=0, facings=[box], descriptor=describe(photo, box), label=label))
                    items, _ = build_items(make_frame(photo), groups, [3], currency=currency, rack_type="shelf")
                    capture = CaptureResult(image_size=photo.size, currency=currency, items=items)
                    updated, report = replace_rack_face(store, capture, "r1")
                    placed = [item for slot in updated.racks[0].slots for item in slot.items]
                    expected = 100 if known else typical_price("soft_drinks", "Cola 500ml", currency)[0]
                    assert [(item.name, item.price) for item in placed] == [("Cola 500ml", expected), ("Mineral Water 500ml", 125)]
                    assert items[0].price_estimated and items[0].price_text == printed
                    assert items[1].price == 125 and not items[1].price_estimated
                    assert report.placed_items == 2 and not report.dropped
                    assert updated.racks[1] == store.racks[1] and store.model_dump_json() == before
                    assert all(0 < item.price <= MAX_PRICE for item in placed)
                    assert len(calls) == 1 and client.get_usage().cached_requests == repeat

    asyncio.run(exercise())


@pytest.mark.parametrize("currency,printed,expected", [
    ("USD", f"{MAX_PRICE}¢", MAX_PRICE), ("KRW", f"{MAX_PRICE}원", MAX_PRICE),
    ("JPY", f"{MAX_PRICE}円", MAX_PRICE), ("USD", f"${MAX_PRICE // 100}", MAX_PRICE // 100 * 100),
    ("USD", f"{MAX_PRICE + 1}¢", None), ("JPY", f"{MAX_PRICE + 1}円", None),
])
def test_explicit_prices_at_safe_integer_boundary(currency, printed, expected):
    assert price_minor_units(ShelfItemLabel(price_text=printed), currency, 200) == expected


@pytest.mark.parametrize("currency", ["KRW", "JPY"])
def test_thousand_unit_interpretation_cannot_exceed_safe_integer_range(currency):
    value = 9_007_199_254_741.5
    result = price_minor_units(ShelfItemLabel(price=value), currency, MAX_PRICE)
    assert result == round(value)
