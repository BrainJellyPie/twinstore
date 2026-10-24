"""Unused grounding narration must not discard an entire photo's usable coordinates."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI
from PIL import Image

from store_emulator.domain.config import LLMConfig
from store_emulator.engine import llm_client
from store_emulator.engine.capture import detect
from store_emulator.engine.capture.frame import make_frame


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("label", [{}, {"label": ""}, {"label": "Tea"}, {"label": None},
    {"label": "A product name repeated " * 6}, {"label": 42}])
@pytest.mark.parametrize("position", [0, 1, 2])
def test_unused_labels_preserve_all_grounded_boxes_and_the_cache(monkeypatch, tmp_path, mode, label, position):
    coordinates = [[100 + 200 * i, 50, 180 + 200 * i, 250] for i in range(3)]
    products = [{"box_2d": box, "label": "Tea"} for box in coordinates]
    products[position] = {"box_2d": coordinates[position], **label}
    original, requests = llm_client.litellm.acompletion, []
    monkeypatch.setattr(detect, "refine_detections", lambda frame, bands, boxes, **kwargs: (boxes, bands))

    def respond(request):
        body = json.loads(request.content)
        requests.append(body)
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop", "message": {
                "role": "assistant", "content": json.dumps({"products": products})}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/grounding-boxes", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            detector = detect.VLMGroundingDetector(client, convention="pixels", max_side=800)
            with Image.new("RGB", (800, 600)) as photo:
                frame = make_frame(photo)
                boxes, bands = await detector.detect(frame, [])
                assert [[b.x1, b.y1, b.x2, b.y2] for b in boxes] == coordinates
                assert all(b.source == "vlm" for b in boxes) and bands == []
                assert await detector.detect(frame, []) == (boxes, bands)
            assert len(requests) == 1 and client.get_usage().cached_requests == 1
            saved = [json.loads(path.read_text())["result"] for path in tmp_path.rglob("*.json")]
            assert len(saved) == 1 and [row["box_2d"] for row in saved[0]["products"]] == coordinates
            assert all(set(row) == {"box_2d"} for row in saved[0]["products"])

    asyncio.run(exercise())
