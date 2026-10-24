"""Out-of-plan fixture boxes cannot silently become stocked boundary tiles."""

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
from tests.engine.test_floorplan_model_geometry import GOOD


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("kind,box", [
    ("shelf", [0, 200, 50, 600]), ("gondola", [950, 200, 1000, 600]),
    ("fridge", [200, 0, 600, 50]), ("freezer", [200, 950, 600, 1000]),
    ("counter", [0, 0, 50, 50]), ("entrance", [0, 200, 50, 600]),
    ("shelf", [0, 200, 100, 600]), ("shelf", [500, 200, 500, 600]),
    ("fridge", [200, 500, 600, 500]), ("freezer", [500, 500, 500, 500]),
])
@pytest.mark.parametrize("outcome", ["corrected", "repeated", "legacy_cache"])
def test_invalid_fixture_is_corrected_before_cache_and_store_build(monkeypatch, tmp_path, mode, kind, box, outcome):
    bad = copy.deepcopy(GOOD)
    bad["fixtures"][0] = {"kind": kind, "box": box, "label": "snacks"}
    original, calls = llm_client.litellm.acompletion, []

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        good = outcome == "legacy_cache" or outcome == "corrected" and len(calls) > 1
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(GOOD if good else bad)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/floorplan-fixture-overlap", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            with Image.new("RGB", (40, 40), "white") as photo:
                if outcome == "legacy_cache":
                    await vlm_read(client, photo)
                    [entry] = list(tmp_path.rglob("*.json"))
                    saved = json.loads(entry.read_text())
                    saved["result"] = bad
                    entry.write_text(json.dumps(saved))
                if outcome == "repeated":
                    with pytest.raises(InstructorRetryException):
                        await vlm_read(client, photo)
                    assert not list(tmp_path.rglob("*.json"))
                else:
                    reading = await vlm_read(client, photo)
                    assert reading.fixtures[0].x1 == pytest.approx(.0625)
                    assert reading.fixtures[0].kind == "fridge" and reading.fixtures[0].label == "drinks"
                    store, _ = plan_to_store(reading)
                    assert not [issue for issue in validate(store) if issue.severity == "error"]
                    assert await vlm_read(client, photo) == reading
                    assert client.get_usage().cached_requests == 1
                    assert [json.loads(p.read_text())["result"] for p in tmp_path.rglob("*.json")] == [GOOD]

    asyncio.run(exercise())
    assert len(calls) == 2


@pytest.mark.parametrize("kind,box,normalized", [
    ("shelf", [50, 200, 300, 600], (0, .125, .25, .625)),
    ("gondola", [300, 600, 50, 200], (0, .125, .25, .625)),
    ("entrance", [100, 200, 100, 400], (0, .125, 0, .375)),
    ("entrance", [200, 900, 400, 900], (.125, 1, .375, 1)),
    ("entrance", [100, 100, 100, 100], (0, 0, 0, 0)),
])
def test_clipped_fixtures_and_boundary_door_lines_remain_supported(kind, box, normalized):
    class Model:
        async def generate_structured_with_image_async(self, schema, *args, **kwargs):
            return schema.model_validate({**GOOD, "fixtures": [{"kind": kind, "box": box}]})

    with Image.new("RGB", (40, 40)) as photo:
        reading = asyncio.run(vlm_read(Model(), photo))
    [fixture] = reading.fixtures
    assert (fixture.x1, fixture.y1, fixture.x2, fixture.y2) == pytest.approx(normalized)
    store, _ = plan_to_store(reading)
    assert not [issue for issue in validate(store) if issue.severity == "error"]
