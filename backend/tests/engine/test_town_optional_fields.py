"""Unspecified optional town suggestions retain known values and declared defaults."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI
from pydantic import ValidationError

from store_emulator.domain.config import LLMConfig
from store_emulator.engine import llm_client
from store_emulator.engine.town_writer import _Draft, describe_town

OPTIONAL = ("name", "rationale", "neighbor_categories", "size_m", "density", "venue_density")
GOOD = dict(name="Campus", rationale="Students nearby.", archetype="university", neighbor_categories=["cafe", "pc_room"],
            size_m=650, density=.8, venue_density=1.7)
DEFAULTS = dict(name="", rationale="", neighbor_categories=[], size_m=800, density=.5, venue_density=1)


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("missing", [*OPTIONAL, "all"])
@pytest.mark.parametrize("competitors", [0, 2])
def test_unknown_optional_values_preserve_town_draft_through_http_and_cache(monkeypatch, tmp_path, mode, missing, competitors):
    fields = OPTIONAL if missing == "all" else (missing,)
    payload = {**GOOD, "n_competitors": competitors, **dict.fromkeys(fields)}
    expected = {**GOOD, "n_competitors": competitors, **{key: DEFAULTS[key] for key in fields}}
    original, calls = llm_client.litellm.acompletion, []

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop", "message": {
                "role": "assistant", "content": json.dumps(payload)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/town-optional", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            result = await describe_town(client, "University street", seed=17)
            assert result.rationale == expected["rationale"]
            assert result.spec.model_dump(mode="json") == {key: value for key, value in {**expected, "seed": 17}.items() if key != "rationale"}
            cached = await describe_town(client, "University street", seed=23)
            assert cached.spec.model_dump(exclude={"seed"}) == result.spec.model_dump(exclude={"seed"})
            assert cached.spec.seed == 23 and len(calls) == 1 and client.get_usage().cached_requests == 1
            saved = json.loads(next(tmp_path.rglob("*.json")).read_text())["result"]
            assert saved == expected

    asyncio.run(exercise())


@pytest.mark.parametrize("change", [{"archetype": None}, {"archetype": "unknown"}, {"size_m": 199}, {"size_m": 3001},
    {"density": -1}, {"density": 2}, {"venue_density": -1}, {"venue_density": 5}, {"size_m": "invalid"},
    {"neighbor_categories": ["unknown"]}, {"neighbor_categories": {}}, {"name": []}, {"rationale": 123},
    {"n_competitors": -1}, {"n_competitors": 61}])
def test_non_null_malformed_values_and_required_archetype_remain_invalid(change):
    with pytest.raises(ValidationError):
        _Draft.model_validate({**GOOD, **change})


@pytest.mark.parametrize("competitors", [None, 0, 60])
def test_omitted_options_and_explicit_competitor_endpoints_remain_valid(competitors):
    assert _Draft(archetype="residential", n_competitors=competitors).n_competitors == competitors
