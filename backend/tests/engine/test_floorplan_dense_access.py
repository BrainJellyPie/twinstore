"""Dense but well-formed model plans must finish their bounded access repair."""

import asyncio
import json
import random
import re

import httpx
import pytest
from openai import AsyncOpenAI
from PIL import Image

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.floorplan import FloorPlanReading, PlanFixture
from store_emulator.engine import llm_client
from store_emulator.engine.floorplan import plan_to_store, vlm_read
from store_emulator.engine.validation import validate


def boxes(style):
    if style in {"rows", "columns"}:
        return [[0, i * 62.5, 1000, (i + 1) * 62.5] if style == "rows" else
                [i * 62.5, 0, (i + 1) * 62.5, 1000] for i in range(0, 16, 2)]
    rng = random.Random(0)
    return [[x * 62.5, y * 62.5, (x + 1) * 62.5, (y + 1) * 62.5]
            for y in range(16) for x in range(16)
            if ((x + y) % 2 == 0 if style == "checker" else rng.random() < .65)]


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("style", ["rows", "columns", "checker", "random"])
def test_dense_http_plan_finishes_access_repair_instead_of_failing_at_forty(monkeypatch, tmp_path, mode, style):
    payload = {"outline": [0, 0, 1000, 1000], "width_m": 20, "depth_m": 20,
               "fixtures": [{"kind": "gondola", "box": box, "label": "snacks"} for box in boxes(style)]}
    original, calls = llm_client.litellm.acompletion, []

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(payload)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/floorplan-dense-access", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            with Image.new("RGB", (40, 40)) as photo:
                reading = await vlm_read(client, photo)
                before = reading.model_dump_json()
                store, notes = plan_to_store(reading)
                assert not [issue for issue in validate(store) if issue.severity == "error"], notes
                cleared = next(int(re.match(r"\d+", note)[0]) for note in notes if "tile(s) cleared" in note)
                assert 0 < cleared < 256
                if style in {"rows", "columns"}:
                    # Eight continuous rows/columns need at most one opening
                    # each, including access around the counter by the door.
                    assert cleared <= 8 and len(store.product_racks) >= 118
                assert not [issue for issue in validate(store) if issue.code == "blocked_slot"]
                assert store.entrances and store.exits and store.counters and store.product_racks
                assert reading.model_dump_json() == before
                cached = await vlm_read(client, photo)
                replay, replay_notes = plan_to_store(cached)
                assert replay.model_dump() == store.model_dump() and replay_notes == notes
                assert len(calls) == 1 and client.get_usage().cached_requests == 1

    asyncio.run(exercise())


@pytest.mark.parametrize("grid", [(8, 8), (16, 16), (16, 8)])
@pytest.mark.parametrize("density", [0, .35, .7, 1])
@pytest.mark.parametrize("corner", [(0, 0), (0, 1), (1, 0), (1, 1)])
def test_access_repair_handles_grid_bounds_all_corners_and_dense_regions(grid, density, corner):
    w, h = grid
    rng = random.Random(20261025)
    fixtures = [PlanFixture(kind="shelf", x1=x / w, y1=y / h, x2=(x + 1) / w, y2=(y + 1) / h)
                for y in range(h) for x in range(w) if rng.random() < density]
    fixtures += [PlanFixture(kind="entrance", x1=corner[0], y1=corner[1], x2=corner[0], y2=corner[1]),
                 PlanFixture(kind="counter", x1=.5, y1=.5, x2=.5 + 1 / w, y2=.5 + 1 / h)]
    reading = FloorPlanReading(width_m=w * 1.25, depth_m=h * 1.25, fixtures=fixtures)
    before = reading.model_dump_json()
    store, notes = plan_to_store(reading)
    assert not [issue for issue in validate(store) if issue.severity == "error" or issue.code == "blocked_slot"], notes
    assert store.grid_size == grid
    assert store.entrances[0].position == store.exits[0].position == (corner[0] * (w - 1), corner[1] * (h - 1))
    assert store.counters[0].position == (w // 2, h // 2)
    assert reading.model_dump_json() == before
