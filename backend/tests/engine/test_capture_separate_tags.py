"""A separate local tag transcription preserves qualifiers and never erases product identity."""
import asyncio
import base64
import io
import json
from types import SimpleNamespace

import httpx
from openai import AsyncOpenAI
from PIL import Image, ImageDraw
import pytest

from store_emulator.domain.capture import CaptureOptions, CaptureResult, ShelfItemLabel
from store_emulator.domain.config import LLMConfig
from store_emulator.engine import llm_client
from store_emulator.engine.capture.bands import Band, Line
from store_emulator.engine.capture.catalog_match import price_minor_units
from store_emulator.engine.capture.detect import Detection
from store_emulator.engine.capture.frame import make_frame
from store_emulator.engine.capture.recognize import FacingGroup, VLMLabeler, describe, label_images


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("tag,currency,size,expected", [
    ("리터당 1,000원", "KRW", "500ml", None),
    ("1,000원 할인", "KRW", "500ml", None),
    ("1,000원", "KRW", "500ml", 1000),
    ("$1.00 / L", "USD", "500ml", None),
    ("$1.00", "USD", "500ml", 100),
    ("$1.00 WITH COUPON", "USD", "500ml", 100),
    ("FREE $0.00", "USD", "500ml", 0),
    ("$1.00 / BOTTLE", "USD", "6 BOTTLES", None),
    ("$6.00 / PACK", "USD", "6 BOTTLES", 600),
    ("Promotion for this week: $1.00 OFF", "USD", "500ml", None),
    ("LIMIT 2 PER CUSTOMER", "USD", "500ml", None),
    ("MAX 2 PER PERSON", "USD", "500ml", None),
    ("MINIMUM 2 PER ORDER", "USD", "500ml", None),
    ("LIMITED OFFER $1.00", "USD", "500ml", 100),
    ("", "USD", "500ml", None),
    (None, "USD", "500ml", None),
])
def test_local_tag_http_schema_conversion_and_cache(monkeypatch, tmp_path, mode, tag, currency, size, expected):
    original, requests = llm_client.litellm.acompletion, []

    def respond(request):
        body = json.loads(request.content)
        requests.append(body)
        user = next(m["content"] for m in body["messages"] if m["role"] == "user")
        url = next(part["image_url"]["url"] for part in user if part["type"] == "image_url")
        image = Image.open(io.BytesIO(base64.b64decode(url.split(",", 1)[1])))
        if len(requests) == 1:
            assert image.size == (100, 80)
            payload = {"name": "Cola", "size": size, "category": "soft drink", "price_text": "$1.00", "price": 1}
        else:
            assert len(requests) == 2 and image.size == (100, 20)
            assert image.getpixel((50, 10))[2] > 240
            if mode == "json_schema":
                schema = body["response_format"]["json_schema"]["schema"]
                assert set(schema["properties"]) == {"literal_text"}
                assert schema["required"] == ["literal_text"]
            payload = {"literal_text": tag}
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(payload)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/separate-tag", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            labeler = VLMLabeler(client, currency=currency, separate_price_tag=True)
            with Image.new("RGB", (100, 80), "red") as image, Image.new("RGB", (100, 20), "blue") as strip:
                for _ in range(2):
                    label = await labeler.label(image, price_tag=strip)
                    assert label.name == "Cola" and label.size == size and label.price is None
                    assert label.price_text == (tag or "")
                    assert price_minor_units(label, currency, 699) == expected
                    assert ShelfItemLabel.model_validate(label.model_dump()).price_text == (tag or "")
                assert len(requests) == 2 and labeler.calls == 4
                assert client.get_usage().cached_requests == 2

    asyncio.run(exercise())


@pytest.mark.parametrize("case", ["missing", "failure", "invalid", "too_long", "cloud"])
def test_unavailable_tag_keeps_identity_and_does_not_reuse_an_unverified_price(case):
    calls = []

    class Reply:
        async def generate_structured_with_image_async(self, schema, system, user, image, **kwargs):
            calls.append(schema)
            if len(calls) == 1:
                return schema(name="Cola", category="soft drink", price_text="$1.00", price=1)
            if case == "failure":
                raise RuntimeError("tag reader unavailable")
            if case == "too_long":
                return schema(literal_text="a" * 201)
            return schema(literal_text={"amount": 1})

    with Image.new("RGB", (100, 80), "red") as image:
        labeler = VLMLabeler(Reply(), currency="USD", separate_price_tag=case != "cloud")
        label = asyncio.run(labeler.label(image, price_tag=None if case == "missing" else image))
    assert label.name == "Cola" and label.category == "soft drink"
    assert price_minor_units(label, "USD", 699) == (100 if case == "cloud" else None)
    assert labeler.calls == len(calls) == (1 if case in {"missing", "cloud"} else 2)


def test_production_price_strip_contains_the_shelf_edge_and_not_the_package():
    with Image.new("RGB", (400, 300), "red") as photo:
        ImageDraw.Draw(photo).rectangle((0, 200, 399, 299), fill="blue")
        before = photo.tobytes()
        frame = make_frame(photo)
        band = Band(0, Line(50, 0, 200), Line(200, 0, 200), 400)
        detection = Detection(100, 50, 200, 190, band=0)
        group = FacingGroup(0, [detection], describe(frame.image, detection))
        combined, tag = label_images(photo, frame, band, group)
        assert tag is not None and tag.getpixel((tag.width // 2, tag.height // 2)) == (0, 0, 255)
        assert tag.getextrema() == ((0, 0), (0, 0), (255, 255))
        assert combined.getpixel((combined.width // 2, 30)) == (255, 0, 0)
        assert photo.tobytes() == before


@pytest.mark.parametrize("base,expected", [("http://127.0.0.1:8082/v1", True), ("http://localhost:11434/v1", True),
    ("http://[::1]:8082/v1", True), ("https://api.openai.com/v1", False), ("", False)])
def test_capture_application_enables_separate_tags_only_for_loopback_models(monkeypatch, base, expected):
    from store_emulator.application import capture

    async def pipeline(photo, **kwargs):
        assert kwargs["labeler"].separate_price_tag is expected
        return SimpleNamespace(result=CaptureResult(image_size=photo.size, currency="USD"))

    monkeypatch.setattr(capture, "capture_shelf", pipeline)
    with Image.new("RGB", (20, 20)) as photo:
        result = capture.run_capture_sync(photo, CaptureOptions(detector="classic", currency="USD"),
                                          LLMConfig(model="openai/test", api_base=base))
    assert result.currency == "USD"
