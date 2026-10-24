"""Unreadable optional shelf-label text must not erase a readable product and price."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI
from PIL import Image
from pydantic import ValidationError

from store_emulator.domain.capture import ShelfItemLabel
from store_emulator.domain.config import LLMConfig
from store_emulator.engine import llm_client
from store_emulator.engine.capture.bands import Band, Line
from store_emulator.engine.capture.detect import Detection
from store_emulator.engine.capture.frame import make_frame
from store_emulator.engine.capture.pipeline import build_items
from store_emulator.engine.capture.recognize import FacingGroup, VLMLabeler, describe


TEXT = ["name", "brand", "size", "category", "price_text"]


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("missing", [*TEXT, "optional", "all", "omitted"])
def test_partial_http_label_survives_grouping_price_conversion_and_cache(monkeypatch, tmp_path, mode, missing):
    answer = dict(name="Tea", brand="Leaf", size="250 ml", category="tea", price_text="$2.49", price=2.49, confidence=8)
    fields = TEXT if missing == "all" else TEXT[1:] if missing == "optional" else [missing]
    if missing == "omitted":
        for key in TEXT[1:]:
            answer.pop(key)
    else:
        for key in fields:
            answer[key] = None
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
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/capture-optional-metadata", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            with Image.new("RGB", (100, 80), "white") as photo:
                frame = make_frame(photo)
                band = Band(0, Line(0, 0, 50), Line(60, 0, 50), 100)
                detection = Detection(x1=10, y1=0, x2=50, y2=60, band=0)
                labeler = VLMLabeler(client, currency="USD")
                for repeat in range(2):
                    group = FacingGroup(band=0, facings=[detection], descriptor=describe(photo, detection))
                    progress = []
                    await labeler.label_groups(photo, frame, [band], [group], on_done=lambda done, total: progress.append((done, total)))
                    assert not group.error and group.label is not None
                    assert group.label.confidence == 8 and group.label.price == 2.49
                    assert progress == [(1, 1)]
                    items, _ = build_items(frame, [group], [3], currency="USD", rack_type="shelf")
                    assert len(items) == 1 and items[0].facings == 1 and len(items[0].boxes) == 1
                    if missing == "all":
                        assert not items[0].labeled and items[0].price_estimated
                    else:
                        assert items[0].labeled and items[0].name == ("Leaf" if missing == "name" else "Tea")
                        assert items[0].price == 249 and not items[0].price_estimated
                    assert len(calls) == 1 and client.get_usage().cached_requests == repeat

    asyncio.run(exercise())


@pytest.mark.parametrize("field", TEXT)
@pytest.mark.parametrize("value", [[], {}, 123])
def test_non_null_text_types_remain_invalid(field, value):
    with pytest.raises(ValidationError):
        ShelfItemLabel.model_validate_json(json.dumps({field: value}), strict=True)


@pytest.mark.parametrize("value", [None, -1, 11, True])
def test_confidence_is_not_guessed(value):
    with pytest.raises(ValidationError):
        ShelfItemLabel.model_validate_json(json.dumps({"confidence": value}), strict=True)
