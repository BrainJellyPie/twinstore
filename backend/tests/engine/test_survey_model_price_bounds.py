"""Survey model prices must fit their final minor-unit representation before caching."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI
from PIL import Image

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.persona import Persona
from store_emulator.engine import llm_client
from store_emulator.engine.marketing.survey import survey_panel


FIELDS = ("too_cheap", "cheap", "expensive", "too_expensive")
PERSON = Persona(id="p1", identity="resident", age_group="30s", gender="Female", description="Nearby resident",
                 intent="Buy groceries", purpose="groceries")


@pytest.mark.parametrize("field", FIELDS)
@pytest.mark.parametrize("currency,factor", [("USD", 100), ("KRW", 1)])
@pytest.mark.parametrize("overflow", [False, True])
@pytest.mark.parametrize("recovers", [False, True])
def test_survey_rejects_unrepresentable_model_prices_before_cache(
    tmp_path, monkeypatch, field, currency, factor, overflow, recovers,
):
    good = dict(zip(FIELDS, [1.0, 2.0, 3.0, 4.0]))
    bad = {**good, field: 1e308 if overflow else 9_007_199_254_740_991 / factor + 1}
    requests = []
    original_completion = llm_client.litellm.acompletion

    async def exercise():
        def respond(request):
            requests.append(json.loads(request.content))
            payload = good if recovers and len(requests) > 1 else bad
            return httpx.Response(200, request=request, json={
                "id": "offline-survey", "object": "chat.completion", "created": 0, "model": "local-model",
                "choices": [{"index": 0, "finish_reason": "stop",
                             "message": {"role": "assistant", "content": json.dumps(payload)}}]})

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            transport = AsyncOpenAI(api_key="offline-test", base_url="http://local.invalid/v1",
                                    http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original_completion(**{**kwargs, "client": transport, "api_key": "offline-test", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/local-survey-test", api_base="http://local.invalid/v1",
                structured_output="json_schema", cache_dir=str(tmp_path), seed=0))
            with Image.new("RGB", (2, 2)) as board:
                args = (client, [PERSON], board, ["price_vw"], 1)
                answers = await survey_panel(*args, currency=currency, minor_per_major=factor)
                assert len(answers) == 1
                if recovers:
                    assert not answers[0].error
                    assert [getattr(answers[0], key) for key in FIELDS] == [n * factor for n in [1, 2, 3, 4]]
                    assert await survey_panel(*args, currency=currency, minor_per_major=factor) == answers
                    assert client.get_usage().cached_requests == 1
                    cached = [json.loads(path.read_text())["result"] for path in tmp_path.rglob("*.json")]
                    assert cached == [good]
                else:
                    assert answers[0].error
                    assert all(getattr(answers[0], key) is None for key in FIELDS)
                    assert not list(tmp_path.rglob("*.json"))

    asyncio.run(exercise())
    assert len(requests) == 2


@pytest.mark.parametrize("currency,factor", [("USD", 100), ("JPY", 1)])
@pytest.mark.parametrize("minor", [0, 1, 9_007_199_254_740_991])
def test_supported_survey_price_boundaries_remain_usable(currency, factor, minor):
    class Model:
        async def generate_structured_with_image_async(self, schema, *args, **kwargs):
            return schema.model_validate(dict.fromkeys(FIELDS, minor / factor))

    with Image.new("RGB", (2, 2)) as board:
        answer = asyncio.run(survey_panel(Model(), [PERSON], board, ["price_vw"], 1,
            currency=currency, minor_per_major=factor))[0]
    assert not answer.error
    assert [getattr(answer, key) for key in FIELDS] == [minor] * 4
