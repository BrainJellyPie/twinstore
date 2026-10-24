"""Unscaled VLM floor plans retain the aspect ratio of the image actually sent."""

import asyncio
import base64
import io
import json

import httpx
import pytest
from openai import AsyncOpenAI
from PIL import Image

from store_emulator.domain.config import LLMConfig
from store_emulator.engine import llm_client
from store_emulator.engine.floorplan import plan_to_store, vlm_read
from store_emulator.engine.validation import validate


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("size,orientation,outline,dimensions,sent,metres,grid", [
    ((800, 400), 1, [100, 100, 900, 900], (0, 0), (800, 400), (12, 6), (10, 8)),
    ((400, 800), 1, [100, 100, 900, 900], (0, 0), (400, 800), (6, 12), (8, 10)),
    ((400, 400), 1, [100, 100, 900, 900], (0, 0), (400, 400), (12, 12), (10, 10)),
    ((800, 400), 1, [250, 0, 750, 1000], (0, 0), (800, 400), (12, 12), (10, 10)),
    ((400, 800), 1, [0, 250, 1000, 750], (0, 0), (400, 800), (12, 12), (10, 10)),
    ((800, 400), 6, [100, 100, 900, 900], (0, 0), (400, 800), (6, 12), (8, 10)),
    ((800, 400), 8, [100, 100, 900, 900], (0, 0), (400, 800), (6, 12), (8, 10)),
    ((1600, 800), 1, [100, 100, 900, 900], (0, 0), (1280, 640), (12, 6), (10, 8)),
    ((800, 400), 1, [100, 100, 900, 900], (15, 15), (800, 400), (15, 15), (12, 12)),
    ((800, 400), 6, [100, 100, 900, 900], (20, 10), (400, 800), (20, 10), (16, 8)),
    ((800, 400), 1, [100, 100, 900, 900], (15, 0), (800, 400), (12, 6), (10, 8)),
    ((1, 1280), 1, [0, 0, 1000, 1000], (0, 0), (1, 1280), (0.01, 12), (8, 10)),
    ((1, 1280), 1, [0, 0, 100, 1000], (0, 0), (1, 1280), (0.0009375, 12), (8, 10)),
])
def test_unscaled_http_plan_preserves_image_geometry_and_cache(
    monkeypatch, tmp_path, mode, size, orientation, outline, dimensions, sent, metres, grid,
):
    ox1, oy1, ox2, oy2 = outline
    dx, dy = ox2 - ox1, oy2 - oy1
    payload = {"outline": outline, "width_m": dimensions[0], "depth_m": dimensions[1], "fixtures": [
        {"kind": "gondola", "box": [ox1 + dx * .3, oy1 + dy * .4, ox1 + dx * .7, oy1 + dy * .5]},
        {"kind": "entrance", "box": [ox1 + dx * .1, oy2, ox1 + dx * .2, oy2]},
    ]}
    original, calls = llm_client.litellm.acompletion, []

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        images = [part["image_url"]["url"] for message in body["messages"]
                  if isinstance(message["content"], list) for part in message["content"] if part["type"] == "image_url"]
        assert len(images) == 1
        with Image.open(io.BytesIO(base64.b64decode(images[0].split(",", 1)[1]))) as wire_image:
            assert wire_image.size == sent
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(payload)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/floorplan-image-aspect", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            with Image.new("RGB", size, "white") as photo:
                photo.getexif()[274] = orientation
                for repeat in range(2):
                    reading = await vlm_read(client, photo)
                    assert (reading.width_m, reading.depth_m) == pytest.approx(metres)
                    assert reading.fixtures[0].x1 == pytest.approx(.3)
                    assert reading.fixtures[0].y2 == pytest.approx(.5)
                    assert reading.fixtures[1].y1 == reading.fixtures[1].y2 == 1
                    assert bool(reading.notes) == (0 in dimensions)
                    store, _ = plan_to_store(reading)
                    assert store.grid_size == grid
                    assert any(r.slots for r in store.racks)
                    assert not [issue for issue in validate(store) if issue.severity == "error"]
                    assert len(calls) == 1 and client.get_usage().cached_requests == repeat

    asyncio.run(exercise())
