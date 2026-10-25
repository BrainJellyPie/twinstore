"""Known design choices survive local-model spelling variations without changing other options."""

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
from store_emulator.engine.layout_brief import _Brief, read_brief, to_options

CHOICES = {
    "style": ("aisles", "loop", "spine", "cross", "plaza", "free_flow", "perimeter", "showroom"),
    "density": ("spacious", "balanced", "dense"),
    "shelf_direction": ("horizontal", "vertical"),
    "entrance": ("left", "center", "right"),
    "gate_wall": ("front", "back", "left", "right"),
    "checkout_placement": ("auto", "near_entrance", "away_from_entrance"),
    "checkout_wall": ("front", "back", "left", "right"),
    "design_theme": ("classic", "warm", "minimal", "industrial", "botanical", "luxury", "coastal", "terracotta", "nordic", "retro"),
    "seating_zone": ("auto", "front", "back", "left", "right", "center", "near_entrance", "away_from_entrance"),
}


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("field,value", [(field, value) for field, values in CHOICES.items() for value in values])
def test_http_known_choices_keep_the_complete_patch_and_current_options(monkeypatch, tmp_path, mode, field, value):
    current = {"width": 12, "height": 10, "excluded_categories": ["coffee"], "style": "aisles",
               "design_colors": {"wall": "#111111", "floor": "#222222"}, "checkouts": 2}
    before = copy.deepcopy(current)
    categories = [("coffee", "Coffee"), ("TeaGreen", "Green Tea")]
    payload = {field: value, "width": 18, "excluded_categories": ["TeaGreen"],
               "design_colors": {"accent": "#ABCDEF"}, "rationale": "Keep Mixed Case Text"}
    expected = to_options(_Brief.model_validate(payload), current, categories)
    payload[field] = f"\u3000{value.upper()}\t"
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
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/layout-brief-spelling", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            args = (client, "Widen the floor, update its design, and exclude Green Tea",
                    {"name": "Store", "grid": [12, 10]}, categories, current)
            for repeat in range(2):
                result = await read_brief(*args)
                assert result == expected and result.options[field] == value
                final = LayoutOptions.model_validate({**current, **result.options})
                assert final.width == 18 and final.height == 10 and final.checkouts == 2
                assert final.excluded_categories == ["TeaGreen", "coffee"]
                assert final.design_colors.model_dump(exclude_none=True) == {
                    "wall": "#111111", "floor": "#222222", "accent": "#abcdef"}
                assert result.rationale == "Keep Mixed Case Text" and not result.warnings
                assert current == before and len(calls) == 1 and client.get_usage().cached_requests == repeat

    asyncio.run(exercise())


@pytest.mark.parametrize("field", CHOICES)
@pytest.mark.parametrize("value", ["unknown", "", "\t", "near entrance", "free-flow", "cosy", 1, True, [], {}])
def test_unknown_designs_internal_separators_and_wrong_types_remain_invalid(field, value):
    with pytest.raises(ValidationError):
        _Brief.model_validate_json(json.dumps({field: value}), strict=True)


@pytest.mark.parametrize("field", CHOICES)
def test_null_retains_the_current_choice_and_direct_options_stay_strict(field):
    canonical = CHOICES[field][0]
    current = {field: canonical, "width": 12}
    result = to_options(_Brief.model_validate_json(json.dumps({field: None, "width": 18}), strict=True), current, [])
    assert result.options == {"width": 18}
    assert LayoutOptions.model_validate({**current, **result.options}).model_dump()[field] == canonical
    with pytest.raises(ValidationError):
        LayoutOptions.model_validate({field: f" {canonical.upper()} "})
