"""Known fixture spelling must preserve the vision reader's geometry and stocking choices."""

import asyncio
import copy
import json

import httpx
import pytest
from openai import AsyncOpenAI
from PIL import Image
from pydantic import ValidationError

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.floorplan import FloorPlanReading, PlanFixture
from store_emulator.engine import llm_client
from store_emulator.engine.floorplan import plan_to_store, vlm_read
from store_emulator.engine.floorplan.read import _VLMPlan
from store_emulator.engine.validation import validate
from tests.engine.test_floorplan_model_geometry import GOOD

KINDS = ("shelf", "gondola", "fridge", "freezer", "counter", "entrance")


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("kind", KINDS)
def test_http_fixture_spelling_keeps_geometry_stock_and_cache(monkeypatch, tmp_path, mode, kind):
    payload = copy.deepcopy(GOOD)
    payload["fixtures"][0]["kind"] = f"\u3000{kind.upper()}\t"
    payload["fixtures"][0]["label"] = "Mixed Case Sign"
    expected = FloorPlanReading(width_m=15, depth_m=15, outline=(.1, .1, .9, .9), reader="vlm", fixtures=[
        PlanFixture(kind=kind, x1=.0625, y1=.0125, x2=.9375, y2=.075, label="Mixed Case Sign"),
        PlanFixture(kind="gondola", x1=.25, y1=.4375, x2=.75, y2=.525),
        PlanFixture(kind="entrance", x1=.025, y1=.975, x2=.125, y2=1),
    ])
    expected_store, expected_notes = plan_to_store(expected)
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
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/floorplan-kind-spelling", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            with Image.new("RGB", (800, 400), "white") as photo:
                for repeat in range(2):
                    reading = await vlm_read(client, photo)
                    assert (reading.width_m, reading.depth_m, reading.reader) == (15, 15, "vlm") and not reading.notes
                    assert reading.outline == pytest.approx(expected.outline)
                    assert [fixture.kind for fixture in reading.fixtures] == [kind, "gondola", "entrance"]
                    for actual, wanted in zip(reading.fixtures, expected.fixtures, strict=True):
                        assert (actual.x1, actual.y1, actual.x2, actual.y2) == pytest.approx((wanted.x1, wanted.y1, wanted.x2, wanted.y2))
                        assert actual.label == wanted.label
                    store, notes = plan_to_store(reading)
                    assert store == expected_store and notes == expected_notes
                    assert not [issue for issue in validate(store) if issue.severity == "error"]
                    assert len(calls) == 1 and client.get_usage().cached_requests == repeat

    asyncio.run(exercise())


@pytest.mark.parametrize("kind", KINDS)
def test_only_an_entrance_can_have_zero_area_after_kind_recovery(kind):
    payload = copy.deepcopy(GOOD)
    payload["fixtures"][0].update(kind=f" {kind.title()} ", box=[100, 100, 100, 100])
    if kind == "entrance":
        assert _VLMPlan.model_validate_json(json.dumps(payload), strict=True).fixtures[0].kind == "entrance"
    else:
        with pytest.raises(ValidationError, match="positive width and height"):
            _VLMPlan.model_validate_json(json.dumps(payload), strict=True)


@pytest.mark.parametrize("kind", [None, "", "wall", "cash desk", "refrigerator", 1, True, [], {}])
def test_unknown_kinds_and_wrong_types_remain_invalid(kind):
    payload = copy.deepcopy(GOOD)
    payload["fixtures"][0]["kind"] = kind
    with pytest.raises(ValidationError):
        _VLMPlan.model_validate_json(json.dumps(payload), strict=True)
