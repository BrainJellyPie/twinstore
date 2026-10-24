"""Optional study narration and comparison notes must not discard valid conjoint axes."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI
from pydantic import ValidationError

from store_emulator.domain.config import LLMConfig
from store_emulator.engine import llm_client
from store_emulator.engine.marketing.conjoint_design import _Draft, design_conjoint


GOOD = {"name": "Tea choices", "product": "Bottled tea", "context": "Choose one tea.",
        "attributes": [{"name": "Sugar", "levels": ["Regular", "Zero"]},
                       {"name": "Pack", "levels": ["Can", "Bottle"]}],
        "prices": [1.49, 1.99], "rationale": "Compare sugar and packaging.", "comparable": ["Tea bottle"]}
OPTIONAL = ("context", "rationale", "comparable")


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("field", [*OPTIONAL, "all", "omitted"])
def test_optional_nulls_preserve_the_study_axes_and_cache(monkeypatch, tmp_path, mode, field):
    payload = dict(GOOD)
    changed = OPTIONAL if field in {"all", "omitted"} else [field]
    for key in changed:
        if field == "omitted":
            payload.pop(key)
        else:
            payload[key] = None
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
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/conjoint-optional-fields", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            products = [("Tea bottle", 199)]
            first = await design_conjoint(client, "Compare these tea choices", "USD", products)
            assert first.name == GOOD["name"] and first.product == GOOD["product"]
            assert [attribute.model_dump() for attribute in first.attributes] == GOOD["attributes"]
            assert first.prices == [149, 199] and first.currency == "USD"
            assert first.comparable == ([] if "comparable" in changed else ["Tea bottle $1.99"])
            for key in ("context", "rationale"):
                assert getattr(first, key) == ("" if key in changed else GOOD[key])
            paths = list(tmp_path.glob("*/*.json"))
            assert len(paths) == 1
            cached = json.loads(paths[0].read_text())
            for key in changed:
                cached["result"][key] = None
            paths[0].write_text(json.dumps(cached))
            assert await design_conjoint(client, "Compare these tea choices", "USD", products) == first
            assert len(calls) == 1 and client.get_usage().cached_requests == 1

    asyncio.run(exercise())


@pytest.mark.parametrize("field,bad", [
    *[(field, bad) for field in ("context", "rationale") for bad in ([], {}, False, 1)],
    *[("comparable", bad) for bad in ("unknown", {}, False)],
    *[(field, None) for field in ("name", "product", "attributes", "prices")],
])
def test_required_study_structure_prices_and_wrong_nonnull_types_remain_invalid(field, bad):
    with pytest.raises(ValidationError):
        _Draft.model_validate_json(json.dumps({**GOOD, field: bad}), strict=True)
