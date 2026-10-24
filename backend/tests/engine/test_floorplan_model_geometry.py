"""Bad model geometry must be corrected before it becomes a cached floor plan."""

import asyncio
import copy
import json

import httpx
import pytest
from instructor.core.exceptions import InstructorRetryException
from openai import AsyncOpenAI
from PIL import Image

from store_emulator.domain.config import LLMConfig
from store_emulator.engine import llm_client
from store_emulator.engine.floorplan import plan_to_store, vlm_read
from store_emulator.engine.validation import validate


GOOD = {"outline": [100, 100, 900, 900], "width_m": 15, "depth_m": 15, "fixtures": [
    {"kind": "fridge", "box": [150, 110, 850, 160], "label": "drinks"},
    {"kind": "gondola", "box": [300, 450, 700, 520], "label": ""},
    {"kind": "entrance", "box": [120, 880, 200, 900], "label": ""}]}


@pytest.mark.parametrize("field,value", [
    ("outline", []), ("outline", [100, 100, 900]), ("outline", [100, 100, 900, 900, 900]),
    ("outline", [100, 100, "NaN", 900]), ("outline", [100, 100, "Infinity", 900]),
    ("outline", [-1, 100, 900, 900]), ("outline", [100, 100, 1001, 900]),
    ("outline", [900, 100, 100, 900]), ("outline", [100, 100, 100, 900]),
    ("outline", [100, 900, 900, 100]), ("outline", [100, 100, 900, 100]),
    ("box", [150, 110, 850]), ("box", [150, 110, 850, 160, 160]),
    ("box", ["NaN", 110, 850, 160]), ("box", [150, "Infinity", 850, 160]),
    ("box", [-1, 110, 850, 160]), ("box", [150, 110, 1001, 160]),
    ("width_m", "Infinity"), ("depth_m", "Infinity"), ("width_m", "NaN"), ("depth_m", -1),
])
@pytest.mark.parametrize("recovers", [False, True])
def test_model_geometry_retry_precedes_cache_and_store_build(tmp_path, monkeypatch, field, value, recovers):
    bad = copy.deepcopy(GOOD)
    (bad["fixtures"][0] if field == "box" else bad)[field] = value
    requests = []
    original_completion = llm_client.litellm.acompletion

    async def exercise():
        def respond(request):
            requests.append(json.loads(request.content))
            payload = GOOD if recovers and len(requests) > 1 else bad
            return httpx.Response(200, request=request, json={
                "id": "offline-plan", "object": "chat.completion", "created": 0, "model": "local-model",
                "choices": [{"index": 0, "finish_reason": "stop",
                             "message": {"role": "assistant", "content": json.dumps(payload)}}]})

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            transport = AsyncOpenAI(api_key="offline-test", base_url="http://local.invalid/v1",
                                    http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original_completion(**{**kwargs, "client": transport, "api_key": "offline-test", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/local-plan-test", api_base="http://local.invalid/v1",
                structured_output="json_schema", cache_dir=str(tmp_path), seed=0))
            with Image.new("RGB", (2, 2)) as photo:
                if recovers:
                    reading = await vlm_read(client, photo)
                    assert await vlm_read(client, photo) == reading
                    store, _ = plan_to_store(reading)
                    assert reading.width_m == reading.depth_m == 15
                    assert len(reading.fixtures) == 3 and store.grid_size == (12, 12)
                    assert not [issue for issue in validate(store) if issue.severity == "error"]
                    assert client.get_usage().cached_requests == 1
                    cached = [json.loads(path.read_text())["result"] for path in tmp_path.rglob("*.json")]
                    assert cached == [GOOD]
                else:
                    with pytest.raises(InstructorRetryException):
                        await vlm_read(client, photo)
                    assert not list(tmp_path.rglob("*.json"))

    asyncio.run(exercise())
    assert len(requests) == 2


def test_unknown_scale_reversed_fixture_corners_and_line_entrance_still_build():
    class Model:
        async def generate_structured_with_image_async(self, schema, *args, **kwargs):
            data = copy.deepcopy(GOOD)
            data["width_m"] = data["depth_m"] = 0
            data["fixtures"][0]["box"] = [850, 160, 150, 110]
            data["fixtures"][2]["box"] = [120, 900, 200, 900]
            return schema.model_validate(data)

    with Image.new("RGB", (2, 2)) as photo:
        reading = asyncio.run(vlm_read(Model(), photo))
    assert reading.width_m == reading.depth_m == 12
    assert len(reading.fixtures) == 3 and reading.fixtures[2].y1 == reading.fixtures[2].y2 == 1
    assert reading.fixtures[0].x1 == pytest.approx(0.0625)
    store, _ = plan_to_store(reading)
    assert not [issue for issue in validate(store) if issue.severity == "error"]
