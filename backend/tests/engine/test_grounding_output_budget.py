"""Whole-photo coordinates need more output than one cropped product's short label."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI
from PIL import Image

from store_emulator.application import capture
from store_emulator.domain.capture import CaptureOptions
from store_emulator.domain.config import SimulationConfig
from store_emulator.engine import llm_client
from store_emulator.engine.capture import detect
from store_emulator.engine.capture.frame import make_frame
from store_emulator.engine.capture.recognize import VLMLabeler


# Measured with the Qwen3.5 tokenizer; no model or tokenizer download is needed by these tests.
TOKENS = {
    (12, "norm1000"): (247, 532), (12, "norm1"): (411, 696), (12, "pixels"): (378, 663),
    (80, "norm1000"): (1727, 3576), (80, "norm1"): (2723, 4572), (80, "pixels"): (2597, 4446),
}


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("count", [12, 80])
@pytest.mark.parametrize("convention", ["norm1000", "norm1", "pixels"])
@pytest.mark.parametrize("pretty", [False, True])
def test_capture_can_finish_coordinate_output_without_raising_per_product_caps(monkeypatch, tmp_path, mode, count, convention, pretty):
    monkeypatch.chdir(tmp_path)
    coordinates = [[10 + i % 8 * 120, 20 + i // 8 * 90, 90 + i % 8 * 120, 90 + i // 8 * 90] for i in range(count)]
    if convention == "norm1":
        coordinates = [[round(v / 1000 + .0005, 4) for v in row] for row in coordinates]
    elif convention == "pixels":
        coordinates = [[round(v * (.768 if i % 2 == 0 else .576), 3) for i, v in enumerate(row)] for row in coordinates]
    payload = {"products": [{"box_2d": row} for row in coordinates]}
    content = json.dumps(payload, indent=2) if pretty else json.dumps(payload, separators=(",", ":"))
    required = TOKENS[count, convention][int(pretty)]
    original, requests = llm_client.litellm.acompletion, []
    monkeypatch.setattr(detect, "refine_detections", lambda frame, bands, boxes, **kwargs: (boxes, bands))

    def resolve(ref, *, base):
        return base.model_copy(update={"model": ref, "api_base": "http://127.0.0.1:8081/v1", "structured_output": mode})

    monkeypatch.setattr(capture, "resolve_model", resolve)

    def respond(request):
        body = json.loads(request.content)
        requests.append(body)
        grounding = "detect products" in body["messages"][0]["content"]
        truncated = grounding and body["max_tokens"] < required
        answer = (content[:32] if truncated else content) if grounding else json.dumps({"name": "Tea", "price": 2.0})
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "length" if truncated else "stop",
                "message": {"role": "assistant", "content": answer}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            model = "openai/qwen3-vl" if convention == "norm1000" else "openai/local-vision"
            config = capture.capture_llm_config(SimulationConfig(), model)
            assert config is not None and config.max_tokens == 320
            client = llm_client.LiteLLMClient(config)
            detector = (detect.VLMGroundingDetector(client, convention="norm1") if convention == "norm1" else
                        capture.choose_detector(CaptureOptions(detector="vlm", model=model), client))
            with Image.new("RGB", (800, 600)) as photo:
                frame = make_frame(photo)
                boxes, bands = await detector.detect(frame, [])
                assert len(boxes) == count and bands == [], "The whole photo was discarded after the label-sized output cap"
                expected = detect.normalize_boxes(coordinates, (768, 576), convention=convention)
                for box, row in zip(boxes, expected, strict=True):
                    assert (box.x1, box.y1, box.x2, box.y2) == pytest.approx(tuple(v / .96 for v in row))
                assert await detector.detect(frame, []) == (boxes, bands)
                assert len(requests) == 1
                label = await VLMLabeler(client, currency="USD").label(photo)
                assert label.name == "Tea" and label.price == 2
            assert required <= requests[0]["max_tokens"] <= 6144
            assert len(requests) == 2 and requests[1]["max_tokens"] == client.max_tokens == 320
            assert client.get_usage().cached_requests == 1

    asyncio.run(exercise())
