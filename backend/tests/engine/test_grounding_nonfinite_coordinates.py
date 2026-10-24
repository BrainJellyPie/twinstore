"""Invalid model coordinates must not become plausible edge-aligned product crops."""

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


@pytest.mark.parametrize("coordinate", range(4))
@pytest.mark.parametrize("number", ["NaN", "Infinity", "-Infinity"])
@pytest.mark.parametrize("recovers", [False, True])
def test_nonfinite_grounding_recovers_or_falls_back_without_caching_bad_boxes(
    tmp_path, monkeypatch, coordinate, number, recovers,
):
    good = {"products": [{"box_2d": [100, 50, 300, 250], "label": "Tea"}]}
    requests, refined = [], []
    original_completion = llm_client.litellm.acompletion

    def keep(frame, bands, boxes, **kwargs):
        refined.extend(boxes)
        return boxes, bands

    monkeypatch.setattr(detect, "refine_detections", keep)

    async def exercise():
        def respond(request):
            requests.append(json.loads(request.content))
            box = [100, 50, 300, 250]
            if not recovers or len(requests) == 1:
                box[coordinate] = number
            payload = {"products": [{"box_2d": box, "label": "Tea"}]}
            return httpx.Response(200, request=request, json={
                "id": "offline-grounding", "object": "chat.completion", "created": 0, "model": "local-model",
                "choices": [{"index": 0, "finish_reason": "stop",
                             "message": {"role": "assistant", "content": json.dumps(payload)}}]})

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            transport = AsyncOpenAI(api_key="offline-test", base_url="http://local.invalid/v1",
                                    http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original_completion(**{**kwargs, "client": transport, "api_key": "offline-test", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/local-grounding-test", api_base="http://local.invalid/v1",
                structured_output="json_schema", cache_dir=str(tmp_path), seed=0))
            detector = detect.VLMGroundingDetector(client, convention="pixels", max_side=800)
            with Image.new("RGB", (800, 600)) as photo:
                frame = make_frame(photo)
                boxes, bands = await detector.detect(frame, [])
                assert bands == []
                if recovers:
                    assert len(boxes) == len(refined) == 1
                    box = boxes[0]
                    assert (box.x1, box.y1, box.x2, box.y2) == (100, 50, 300, 250)
                    assert await detector.detect(frame, []) == (boxes, bands)
                    assert client.get_usage().cached_requests == 1
                    cached = [json.loads(path.read_text())["result"] for path in tmp_path.rglob("*.json")]
                    assert cached == [good]
                else:
                    assert not boxes and not refined  # existing capture pipeline falls back to classic detection
                    assert not list(tmp_path.rglob("*.json"))

    asyncio.run(exercise())
    assert len(requests) == 2
