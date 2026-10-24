"""Valid multi-fixture floor plans must fit the reader's completion ceiling."""

import json

import httpx
import pytest
from openai import AsyncOpenAI
from PIL import Image, ImageDraw

from store_emulator.application import floorplan
from store_emulator.application.errors import AppError
from store_emulator.domain.config import LLMConfig, SimulationConfig
from store_emulator.engine import llm_client


# Compact / indented payload counts measured with the existing Qwen3.5 tokenizer.
TOKENS = {
    (8, "drinks"): (229, 519), (8, "냉장 음료"): (237, 527),
    (40, "drinks"): (1085, 2399), (40, "냉장 음료"): (1125, 2439),
    (80, "drinks"): (2155, 4749), (80, "냉장 음료"): (2235, 4829),
}


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("reader", ["auto", "vlm"])
@pytest.mark.parametrize("count", [8, 40, 80])
@pytest.mark.parametrize("label", ["drinks", "냉장 음료"])
@pytest.mark.parametrize("pretty", [False, True])
def test_floorplan_reader_retains_every_fixture_with_its_own_output_budget(monkeypatch, tmp_path, mode, reader, count, label, pretty):
    coordinates = [[10 + i % 8 * 120, 20 + i // 8 * 90, 90 + i % 8 * 120, 90 + i // 8 * 90] for i in range(count)]
    payload = {"outline": [0, 0, 1000, 1000], "width_m": 12, "depth_m": 9,
               "fixtures": [{"kind": "shelf", "box": box, "label": label} for box in coordinates]}
    content = json.dumps(payload, ensure_ascii=False, indent=2) if pretty else json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    required = TOKENS[count, label][int(pretty)]
    original, requests = llm_client.litellm.acompletion, []
    config = LLMConfig(model="openai/local-plan", api_base="http://127.0.0.1:8081/v1", max_tokens=320,
                       structured_output=mode, cache_dir=str(tmp_path), seed=0)
    monkeypatch.setattr(floorplan, "capture_llm_config", lambda *args: config)

    def respond(request):
        body = json.loads(request.content)
        requests.append(body)
        truncated = body["max_tokens"] < required
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "length" if truncated else "stop",
                "message": {"role": "assistant", "content": content[:32] if truncated else content}}]})

    async def completion(**kwargs):
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)
            return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

    monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
    with Image.new("RGB", (400, 300), "white") as photo:
        ImageDraw.Draw(photo).rectangle((12, 12, 388, 288), outline="black", width=3)
        result = floorplan.read_plan(photo, reader, "local", SimulationConfig())
        assert result.reader == config.model, "A valid plan incorrectly fell back to geometry-only recognition"
        assert len(result.fixtures) == count and result.width_m == 12 and result.depth_m == 9
        for fixture, box in zip(result.fixtures, coordinates, strict=True):
            assert fixture.kind == "shelf" and fixture.label == label
            assert (fixture.x1, fixture.y1, fixture.x2, fixture.y2) == tuple(value / 1000 for value in box)
        assert floorplan.read_plan(photo, reader, "local", SimulationConfig()) == result
    assert len(requests) == 1 and required <= requests[0]["max_tokens"] <= 6144
    assert config.max_tokens == 320


@pytest.mark.parametrize("reader", ["auto", "vlm"])
def test_model_failure_keeps_explicit_error_and_automatic_fallback(monkeypatch, reader):
    calls = []

    class Model:
        def __init__(self, config):
            pass

        async def generate_structured_with_image_async(self, *args, **kwargs):
            calls.append(kwargs)
            raise ValueError("offline incomplete response")

    monkeypatch.setattr(floorplan, "capture_llm_config", lambda *args: LLMConfig(model="openai/local"))
    monkeypatch.setattr(floorplan, "LiteLLMClient", Model)
    with Image.new("RGB", (400, 300), "white") as photo:
        ImageDraw.Draw(photo).rectangle((12, 12, 388, 288), outline="black", width=3)
        if reader == "vlm":
            with pytest.raises(AppError, match="could not read the plan"):
                floorplan.read_plan(photo, reader, "local", SimulationConfig())
        else:
            result = floorplan.read_plan(photo, reader, "local", SimulationConfig())
            assert result.reader == "classic" and any("vision model unavailable" in note for note in result.notes)
    assert len(calls) == 1 and calls[0]["max_retries"] == 2
