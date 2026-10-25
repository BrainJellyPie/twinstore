"""Automatic placement and audits preserve model-read variants instead of fuzzy-merging SKUs."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI
from PIL import Image

from store_emulator.domain.capture import CaptureResult, ShelfItemLabel
from store_emulator.domain.config import LLMConfig
from store_emulator.domain.rack import SlotItem
from store_emulator.engine import llm_client
from store_emulator.engine.capture.detect import Detection
from store_emulator.engine.capture.frame import make_frame
from store_emulator.engine.capture.pipeline import build_items
from store_emulator.engine.capture.planogram import add_capture_racks, display_name, replace_rack_face
from store_emulator.engine.capture.recognize import FacingGroup, VLMLabeler, describe
from store_emulator.engine.prompting import display_price
from store_emulator.engine.shelf_lab.audit import match_field
from tests.engine.test_rival_comparison_boundaries import pair


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("currency", ["USD", "KRW"])
@pytest.mark.parametrize("estimated", [False, True])
@pytest.mark.parametrize("stored,name,brand,size", [
    ("Coca-Cola Original 500ml", "Coca-Cola Original 1500ml", "", ""),
    ("Organic Full Cream Vanilla Yogurt 500g", "Organic Full Cream Banana Yogurt 500g", "", ""),
    ("Tea", "Tea", "Different Brand", "500ml"),
    ("Milk", "Milk", "", "1500ml"),
])
def test_read_product_identity_survives_placement_and_audit(monkeypatch, tmp_path, mode, currency, estimated, stored, name, brand, size):
    store, _ = pair(our_name=stored, our_price=100)
    store.currency = currency
    store.racks[0].slots[0].items.append(SlotItem(sku="coffee", name="Coffee", price=200))
    before = store.model_dump()
    answer = dict(name=name, brand=brand, size=size, category="soft drink", confidence=9,
                  price=None, price_text="" if estimated else display_price(399, currency))
    original, calls = llm_client.litellm.acompletion, []

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop", "message": {
                "role": "assistant", "content": json.dumps(answer)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/capture-distinct", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            with Image.new("RGB", (100, 80), "white") as photo:
                labeler = VLMLabeler(client, currency=currency)
                for repeat in range(2):
                    labels = [await labeler.label(photo), ShelfItemLabel(name="Coffee", price_text=display_price(125, currency))]
                    groups = []
                    for index, label in enumerate(labels):
                        box = Detection(x1=index * 50, y1=0, x2=index * 50 + 40, y2=60, band=0)
                        groups.append(FacingGroup(band=0, facings=[box], descriptor=describe(photo, box), label=label))
                    items, _ = build_items(make_frame(photo), groups, [1], currency=currency, rack_type="shelf")
                    capture = CaptureResult(image_size=photo.size, currency=currency, items=items)
                    snapshot = capture.model_dump()
                    expected = [(items[0].sku, display_name(items[0]), items[0].price), ("coffee", "Coffee", 125)]
                    assert items[0].price_estimated is estimated and items[0].sku != "tea"
                    audited = match_field(store, capture)
                    assert [(item.sku, display_name(item), item.price) for item in audited.items] == expected
                    for operation in ("replace", "add"):
                        updated, report = (replace_rack_face(store, capture, "r") if operation == "replace"
                                           else add_capture_racks(store, [capture]))
                        placed = [item for rack in updated.racks if rack.id in report.rack_ids
                                  for slot in rack.slots for item in slot.items]
                        assert [(item.sku, item.name, item.price) for item in placed] == expected
                        assert report.placed_items == 2 and not report.dropped
                        if operation == "add":
                            assert updated.racks[0] == store.racks[0]
                    assert capture.model_dump() == snapshot and store.model_dump() == before
                    assert len(calls) == 1 and client.get_usage().cached_requests == repeat

    asyncio.run(exercise())
