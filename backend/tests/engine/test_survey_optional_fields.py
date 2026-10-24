"""Unknown optional fields must not discard an otherwise usable automatic concept-test draft."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI
from pydantic import ValidationError

from store_emulator.domain.config import LLMConfig
from store_emulator.engine import llm_client
from store_emulator.engine.marketing.survey_design import _Draft, design_survey


GOOD = {"name": "Tea concept", "images": ["Tea pack"], "questions": ["appeal", "open"],
        "context": "Compare the pack.", "reference_price": 1.99, "age_groups": ["20s"],
        "genders": ["Female"], "rationale": "Understand pack appeal."}
OPTIONAL = ("images", "age_groups", "genders", "context", "rationale")


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("field", [*OPTIONAL, "all", "omitted"])
def test_optional_nulls_preserve_the_draft_and_cache(monkeypatch, tmp_path, mode, field):
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
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/concept-optional-fields", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            packages = [("Tea pack", "asset-tea", "Tea Co", "Tea at $1.99")]
            first = await design_survey(client, "How appealing is this tea pack?", "USD", packages)
            assert first.name == GOOD["name"] and first.questions == ["appeal", "open"]
            assert first.reference_price == 199 and first.currency == "USD"
            assert first.stimuli == ([] if "images" in changed else ["asset-tea"])
            assert bool(first.warnings) == ("images" in changed)
            for key in ("context", "rationale", "age_groups", "genders"):
                assert getattr(first, key) == (("" if key in {"context", "rationale"} else []) if key in changed else GOOD[key])
            # The existing cache validation boundary must also accept optional nulls.
            paths = list(tmp_path.glob("*/*.json"))
            assert len(paths) == 1
            cached = json.loads(paths[0].read_text())
            for key in changed:
                cached["result"][key] = None
            paths[0].write_text(json.dumps(cached))
            assert await design_survey(client, "How appealing is this tea pack?", "USD", packages) == first
            assert len(calls) == 1 and client.get_usage().cached_requests == 1

    asyncio.run(exercise())


@pytest.mark.parametrize("field,bad", [
    *[(field, bad) for field in ("images", "age_groups", "genders") for bad in ("unknown", {}, False)],
    *[(field, bad) for field in ("context", "rationale") for bad in ([], {}, False, 1)],
    ("name", None), ("questions", None),
])
def test_required_and_malformed_nonnull_fields_stay_strict(field, bad):
    with pytest.raises(ValidationError):
        _Draft.model_validate_json(json.dumps({**GOOD, field: bad}), strict=True)
