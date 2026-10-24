"""Unknown optional brief fields must preserve valid edits and existing layout choices."""

import asyncio
import copy
import json

import httpx
import pytest
from openai import AsyncOpenAI
from pydantic import ValidationError

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.layout_options import LayoutOptions
from store_emulator.engine import llm_client
from store_emulator.engine.layout_brief import _Brief, read_brief


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("missing", ["excluded_categories", "not_expressible", "rationale", "all", "omitted"])
@pytest.mark.parametrize("width", [18, 100])
def test_optional_nulls_keep_valid_options_and_current_exclusions(monkeypatch, tmp_path, mode, missing, width):
    current = {"width": 12, "height": 10, "excluded_categories": ["coffee"],
               "design_colors": {"wall": "#111111", "floor": "#222222", "accent": "#333333"}}
    before = copy.deepcopy(current)
    payload = {"width": width, "depth": 12, "style": "loop", "design_colors": {"accent": "#ABCDEF"}}
    if missing != "omitted":
        for field in ["excluded_categories", "not_expressible", "rationale"] if missing == "all" else [missing]:
            payload[field] = None
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
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/layout-brief-optional-fields", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            args = (client, f"Make it {width} by 12, a loop, change the accent to #abcdef",
                    {"name": "Store", "grid": [12, 10]}, [("coffee", "Coffee"), ("tea", "Tea")], current)
            result = await read_brief(*args)
            assert result.options["style"] == "loop" and result.options["height"] == 12
            assert result.options["design_colors"] == {**current["design_colors"], "accent": "#abcdef"}
            assert "excluded_categories" not in result.options and not result.not_expressible and not result.rationale
            final = LayoutOptions.model_validate({**current, **result.options})
            assert final.excluded_categories == ["coffee"]
            assert final.width == (18 if width == 18 else 12) and final.height == 12
            assert bool(result.warnings) is (width == 100)
            assert current == before
            assert await read_brief(*args) == result
            assert len(calls) == 1 and client.get_usage().cached_requests == 1

    asyncio.run(exercise())


@pytest.mark.parametrize("field,value", [
    ("excluded_categories", "coffee"), ("excluded_categories", [None]), ("excluded_categories", {}),
    ("not_expressible", "Lighting"), ("not_expressible", [123]), ("rationale", []), ("rationale", 123),
    ("style", "zigzag"), ("width", "eighteen"),
])
def test_wrong_non_null_values_are_not_silently_ignored(field, value):
    with pytest.raises(ValidationError):
        _Brief.model_validate_json(json.dumps({field: value}), strict=True)
