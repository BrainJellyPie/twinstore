"""Visible shelf products remain readable when their price strip lies outside a photo."""

import asyncio
import base64
import io
import json

import httpx
import pytest
from openai import AsyncOpenAI
from PIL import Image, ImageDraw

from store_emulator.domain.config import LLMConfig
from store_emulator.engine import llm_client
from store_emulator.engine.capture.bands import Band, Line
from store_emulator.engine.capture.detect import ClassicDetector, Detection
from store_emulator.engine.capture.frame import make_frame
from store_emulator.engine.capture.pipeline import capture_shelf
from store_emulator.engine.capture.recognize import FacingGroup, VLMLabeler, describe, label_images


def shelf_photo(angle, cut):
    photo = Image.new("RGB", (500, 400), "white")
    draw = ImageDraw.Draw(photo)
    for y in (20, 140, 260, 380):
        for x in range(10, 490, 45):
            draw.rectangle((x, y, x + 36, y + 95), fill=(40 + x % 120, 75 + y % 130, 130))
            draw.line((x + 5, y + 20, x + 30, y + 20), fill="white", width=5)
        draw.rectangle((0, y + 100, 500, y + 108), fill="black")
    return photo.rotate(angle, expand=False, fillcolor="white").crop((0, 0, 500, 400 - cut))


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("angle", [-6, 6])
@pytest.mark.parametrize("cut", [0, 35])
def test_http_capture_reads_visible_products_even_without_a_price_strip(monkeypatch, tmp_path, mode, angle, cut):
    photo = shelf_photo(angle, cut)
    before = photo.tobytes()
    original, requests = llm_client.litellm.acompletion, []

    def respond(request):
        body = json.loads(request.content)
        message = next(m for m in body["messages"] if m["role"] == "user")
        url = next(p["image_url"]["url"] for p in message["content"] if p["type"] == "image_url")
        image = Image.open(io.BytesIO(base64.b64decode(url.split(",", 1)[1]))).convert("RGB")
        assert image.width > 0 and image.height > 1
        requests.append(url)
        payload = {"name": "Visible package", "category": "chips", "price_text": "", "price": None, "confidence": 8}
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop", "message": {
                "role": "assistant", "content": json.dumps(payload)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/capture-border", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path), max_tokens=320))
            previous_calls = None
            for _ in range(2):
                run = await capture_shelf(photo, detector=ClassicDetector(), labeler=VLMLabeler(client, currency="USD"))
                assert len(run.result.items) == 33
                assert all(item.labeled and item.name == "Visible package" for item in run.result.items)
                assert all(item.price_estimated for item in run.result.items)
                assert all(group.label is not None and not group.error for group in run.groups)
                assert run.result.vlm_calls == 33
                for item in run.result.items:
                    assert all(0 <= b.x1 <= b.x2 <= photo.width and 0 <= b.y1 <= b.y2 <= photo.height for b in item.boxes)
                if previous_calls is not None:
                    assert len(requests) == previous_calls
                previous_calls = len(requests)
            assert client.get_usage().cached_requests >= 33
            assert photo.tobytes() == before

    asyncio.run(exercise())


@pytest.mark.parametrize("angle", [-15, 0, 15])
@pytest.mark.parametrize("box", [(-100, 50, -50, 100), (450, 50, 500, 100), (50, -100, 100, -50),
                                (50, 350, 100, 400), (-20, -30, 420, 330), (40, 50, 100, 150)])
def test_work_frame_boxes_are_ordered_and_clipped_at_every_edge(angle, box):
    frame = make_frame(Image.new("RGB", (400, 300), "white"), angle=angle, max_side=200)
    mapped = frame.to_image_box(*box)
    assert 0 <= mapped.x1 <= mapped.x2 <= 400
    assert 0 <= mapped.y1 <= mapped.y2 <= 300


@pytest.mark.parametrize("bottom", [300, 301, 350])
def test_missing_price_strip_is_white_and_keeps_the_visible_package(bottom):
    photo = Image.new("RGB", (400, 300), "red")
    frame = make_frame(photo)
    band = Band(0, Line(150, 0, 200), Line(bottom, 0, 200), 400)
    detection = Detection(100, 150, 160, 290, band=0)
    group = FacingGroup(0, [detection], describe(frame.image, detection))
    image, price_tag = label_images(photo, frame, band, group)
    assert price_tag is None
    assert image.getpixel((image.width // 2, 30)) == (255, 0, 0)
    assert image.getpixel((image.width // 2, image.height - 1)) == (255, 255, 255)


@pytest.mark.parametrize("box", [(-80, 50, -40, 130), (420, 50, 460, 130), (50, -80, 100, -40), (50, 320, 100, 360)])
def test_a_product_entirely_outside_the_photo_is_not_sent_as_an_empty_image(box):
    photo = Image.new("RGB", (400, 300), "red")
    frame = make_frame(photo)
    band = Band(0, Line(0, 0, 200), Line(250, 0, 200), 400)
    detection = Detection(*box, band=0)
    group = FacingGroup(0, [detection], describe(frame.image, detection))
    with pytest.raises(ValueError, match="visible product"):
        label_images(photo, frame, band, group)
