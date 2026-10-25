"""Absent normalized names must never merge captured goods into an unrelated store SKU."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI
from PIL import Image

from store_emulator.domain.capture import CaptureResult, ShelfItemLabel
from store_emulator.domain.config import LLMConfig
from store_emulator.engine import llm_client
from store_emulator.engine.capture.detect import Detection
from store_emulator.engine.capture.frame import make_frame
from store_emulator.engine.capture.pipeline import build_items
from store_emulator.engine.capture.planogram import PlacementReport, match_store_skus
from store_emulator.engine.capture.recognize import FacingGroup, VLMLabeler, describe
from tests.engine.test_capture_ambiguous_sku_matching import match
from tests.engine.test_scenario_target_matching import target_store


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("exact", [False, True])
@pytest.mark.parametrize("name", ["???", "—", "..."])
@pytest.mark.parametrize("stored_name", ["", " !!! "])
def test_unknown_http_label_keeps_its_identity_and_price_while_neighbor_matches(monkeypatch, tmp_path, mode, exact, name, stored_name):
    store = target_store()
    store.racks[0].slots[0].items[0].name = stored_name
    store.racks[0].slots[0].items[0].price = 999
    store.racks[0].slots[0].items[1].name = "Green Tea"
    original, calls = llm_client.litellm.acompletion, []

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        payload = {"name": name, "price": None, "confidence": 8}
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(payload)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/capture-empty-name", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            with Image.new("RGB", (100, 80), "white") as image:
                labeler = VLMLabeler(client, currency="USD")
                for repeat in range(2):
                    bad = await labeler.label(image)
                    groups = []
                    for index, label in enumerate([bad, ShelfItemLabel(name="Green Tea", price=2.49, price_text="$2.49", confidence=8)]):
                        box = Detection(x1=index * 50, y1=0, x2=index * 50 + 40, y2=60, band=0)
                        groups.append(FacingGroup(band=0, facings=[box], descriptor=describe(image, box), label=label))
                    items, _ = build_items(make_frame(image), groups, [3], currency="USD", rack_type="shelf")
                    captured = CaptureResult(image_size=image.size, items=items)
                    before = store.model_dump_json(), captured.model_dump_json()
                    report = PlacementReport()
                    result = match_store_skus(store, captured, report, exact=exact)
                    assert result.items[0] == items[0] and result.items[0].sku != "s-cola"
                    assert result.items[0].price is None and result.items[0].price_estimated
                    assert result.items[1].sku == "s-zero" and result.items[1].price == 249
                    assert report.notes == ["1 product(s) matched items the store already sells and keep their SKU"]
                    assert before == (store.model_dump_json(), captured.model_dump_json())
                    assert len(calls) == 1 and client.get_usage().cached_requests == repeat

    asyncio.run(exercise())


@pytest.mark.parametrize("exact", [False, True])
@pytest.mark.parametrize("name", ["", " \u3000", "???", "—"])
def test_a_cleared_or_unusable_label_does_not_match_the_unknown_product_placeholder(exact, name):
    item, report = match([("blank", "", 100), ("placeholder", "Unknown product", 200)], name=name, exact=exact, estimated=True)
    assert item.sku == "captured" and item.name == name and item.price == 500
    assert not report.notes


@pytest.mark.parametrize("exact", [False, True])
def test_an_all_blank_catalog_has_no_identity_to_reuse(exact):
    item, report = match([("blank", "", 100), ("punctuation", "!!!", 200)], name="???", exact=exact, estimated=True)
    assert item.sku == "captured" and item.price == 500 and not report.notes
