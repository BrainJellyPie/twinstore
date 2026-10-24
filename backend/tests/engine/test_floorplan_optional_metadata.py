"""Unknown scale and fixture names do not discard otherwise valid model geometry."""

import asyncio
import copy
import json

import httpx
import pytest
from openai import AsyncOpenAI
from PIL import Image
from pydantic import ValidationError

from store_emulator.domain.config import LLMConfig
from store_emulator.engine import llm_client
from store_emulator.engine.floorplan import plan_to_store, vlm_read
from store_emulator.engine.floorplan.read import _VLMPlan
from store_emulator.engine.validation import validate
from tests.engine.test_floorplan_model_geometry import GOOD


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("dimensions,label,metres", [
    ({}, None, (12, 6)),
    ({"width_m": None, "depth_m": None}, None, (12, 6)),
    ({"width_m": 20, "depth_m": None}, "음료", (12, 6)),
    ({"width_m": None, "depth_m": 10}, "", (12, 6)),
    ({"width_m": 20, "depth_m": 10}, None, (20, 10)),
    ({"width_m": 0, "depth_m": 0}, " 음료 ", (12, 6)),
])
def test_unknown_metadata_preserves_http_geometry_stock_and_cache(monkeypatch, tmp_path, mode, dimensions, label, metres):
    payload = copy.deepcopy(GOOD)
    payload.pop("width_m")
    payload.pop("depth_m")
    payload.update(dimensions)
    payload["fixtures"][0]["label"] = label
    # Omitted labels still use the same empty default.
    payload["fixtures"][1].pop("label")
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
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/floorplan-optional-metadata", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            with Image.new("RGB", (800, 400), "white") as photo:
                for repeat in range(2):
                    reading = await vlm_read(client, photo)
                    assert (reading.width_m, reading.depth_m) == metres
                    assert bool(reading.notes) == (metres == (12, 6))
                    assert reading.reader == "vlm" and len(reading.fixtures) == 3
                    assert reading.fixtures[0].kind == "fridge"
                    assert reading.fixtures[0].x1 == pytest.approx(.0625)
                    assert reading.fixtures[0].label == (label or "").strip()
                    assert reading.fixtures[1].label == ""
                    store, _ = plan_to_store(reading)
                    assert any(r.slots for r in store.racks)
                    assert not [issue for issue in validate(store) if issue.severity == "error"]
                    assert len(calls) == 1 and client.get_usage().cached_requests == repeat

    asyncio.run(exercise())


@pytest.mark.parametrize("field,value", [
    ("outline", None), ("outline", []), ("fixtures", None),
    ("box", None), ("kind", None), ("label", []), ("label", {}), ("label", 123), ("label", "x" * 61),
    ("width_m", "unknown"), ("width_m", -1), ("width_m", "NaN"),
    ("depth_m", []), ("depth_m", -1), ("depth_m", "Infinity"),
])
def test_missing_geometry_and_malformed_nonnull_metadata_stay_invalid(field, value):
    payload = copy.deepcopy(GOOD)
    (payload["fixtures"][0] if field in {"box", "kind", "label"} else payload)[field] = value
    with pytest.raises(ValidationError):
        _VLMPlan.model_validate(payload)
