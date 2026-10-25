"""Unidentifiable model labels must not collapse different photographed goods into one SKU."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI
from PIL import Image

from store_emulator.domain.capture import ShelfItemLabel
from store_emulator.domain.config import LLMConfig
from store_emulator.engine import llm_client
from store_emulator.engine.capture.detect import Detection
from store_emulator.engine.capture.frame import make_frame
from store_emulator.engine.capture.pipeline import build_items
from store_emulator.engine.capture.recognize import FacingGroup, VLMLabeler, describe


def groups_for(image, labels):
    groups = []
    for index, label in enumerate(labels):
        box = Detection(x1=index * 50, y1=0, x2=index * 50 + 40, y2=60, band=0)
        groups.append(FacingGroup(band=0, facings=[box], descriptor=describe(image, box), label=label))
    return groups


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("name", ["???", "...", "—"])
@pytest.mark.parametrize("size", ["", "500 ml"])
def test_two_unidentified_products_keep_separate_stable_ids_and_printed_prices(monkeypatch, tmp_path, mode, name, size):
    original, calls = llm_client.litellm.acompletion, []

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        assert len(calls) <= 2
        price = [1.99, 7.99][len(calls) - 1]
        payload = {"name": name, "size": size, "price": price, "price_text": f"${price:.2f}", "confidence": 8}
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(payload)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/capture-anonymous", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            with Image.new("RGB", (100, 80), "red") as photo:
                photo.paste("green", (50, 0, 100, 80))
                frame = make_frame(photo)
                labeler = VLMLabeler(client, currency="USD")
                previous = None
                for repeat in range(2):
                    labels = []
                    for x in (0, 50):
                        with photo.crop((x, 0, x + 40, 60)) as crop:
                            labels.append(await labeler.label(crop))
                    groups = groups_for(photo, labels)
                    items, _ = build_items(frame, groups, [3], currency="USD", rack_type="shelf", salt="capture-one")
                    assert len({item.sku for item in items}) == 2
                    assert all(item.sku.startswith("cap_u") for item in items)
                    assert [item.price for item in items] == [199, 799]
                    assert all(item.name == name and item.size == size and item.labeled and not item.price_estimated for item in items)
                    assert items == previous if repeat else previous is None
                    previous = items
                    other, _ = build_items(frame, groups, [3], currency="USD", rack_type="shelf", salt="capture-two")
                    assert {item.sku for item in items}.isdisjoint(item.sku for item in other)
                    assert [item.price for item in other] == [199, 799]
                    assert len(calls) == 2 and client.get_usage().cached_requests == repeat * 2

    asyncio.run(exercise())


@pytest.mark.parametrize("label", [ShelfItemLabel(name="Green Tea", size="500 ml"), ShelfItemLabel(name="", brand="Leafy"),
                                  ShelfItemLabel(name="???", brand="Leafy"), ShelfItemLabel(name="녹차", size="500 ml")])
def test_named_or_branded_products_keep_their_existing_cross_capture_identity(label):
    with Image.new("RGB", (100, 80)) as photo:
        frame, groups = make_frame(photo), groups_for(photo, [label, label])
        first, _ = build_items(frame, groups, [3], currency="USD", rack_type="shelf", salt="one")
        second, _ = build_items(frame, groups, [3], currency="USD", rack_type="shelf", salt="two")
    assert len({item.sku for item in [*first, *second]}) == 1
    assert all(not item.sku.startswith("cap_u") for item in first)
