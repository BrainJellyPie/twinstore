"""Draft choice spelling must not change the questionnaire or its intended respondent groups."""

import asyncio
import copy
import json

import httpx
import pytest
from openai import AsyncOpenAI
from pydantic import ValidationError

from store_emulator.application.marketing import _quota
from store_emulator.domain.config import LLMConfig
from store_emulator.domain.marketing import SurveyRequest
from store_emulator.domain.persona import AGE_GROUPS, GENDERS
from store_emulator.engine import llm_client
from store_emulator.engine.marketing.survey_design import _Draft, design_survey, to_design
from tests.engine.test_llm_engine_offline import _persona
from tests.engine.test_survey_optional_fields import GOOD

CHOICES = {"questions": ["purchase_intent", "appeal", "value", "uniqueness", "price_vw", "preference", "open"],
           "age_groups": AGE_GROUPS, "genders": GENDERS}


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("field,value", [(field, value) for field, values in CHOICES.items() for value in values])
def test_http_known_choices_keep_questions_images_prices_and_real_quota(monkeypatch, tmp_path, mode, field, value):
    packages = [("Tea pack", "asset-tea", "Tea Co", "Tea at $1.99"), ("New pack", "asset-new", "Tea Co", "New tea")]
    payload = copy.deepcopy(GOOD)
    payload["images"] = ["Tea pack", "New pack"]
    payload[field] = [value]
    expected = to_design(_Draft.model_validate(payload), [(row[0], row[1]) for row in packages], "USD")
    payload[field] = [f"\u3000{value.swapcase()}\t"]
    personas = [_persona().model_copy(update={"id": f"{age}-{gender}", "age_group": age, "gender": gender})
                for age in AGE_GROUPS for gender in GENDERS]
    before = [persona.model_dump() for persona in personas]
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
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/survey-design-spelling", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            for repeat in range(2):
                result = await design_survey(client, "Compare these two packs with the requested customer group", "USD", packages)
                assert result == expected and result.stimuli == ["asset-tea", "asset-new"]
                assert result.reference_price == 199 and not result.warnings
                request = SurveyRequest.model_validate(result.model_dump())
                assert [p.id for p in _quota(personas, request)] == [
                    f"{age}-{gender}" for age in expected.age_groups for gender in expected.genders]
                assert [persona.model_dump() for persona in personas] == before
                assert len(calls) == 1 and client.get_usage().cached_requests == repeat

    asyncio.run(exercise())


@pytest.mark.parametrize("field", CHOICES)
@pytest.mark.parametrize("value", ["unknown", "", "purchase intent", "20대", "woman", 1, True, None, [], {}])
def test_unlisted_labels_and_wrong_list_item_types_stay_invalid(field, value):
    with pytest.raises(ValidationError):
        _Draft.model_validate_json(json.dumps({**GOOD, field: [value]}), strict=True)


def test_existing_choice_order_deduplication_and_optional_quota_defaults_remain():
    draft = _Draft.model_validate_json(json.dumps({**GOOD, "questions": [" OPEN ", "open", "Appeal"],
                                                 "age_groups": ["20S", "20s"], "genders": ["male", "Male"]}), strict=True)
    result = to_design(draft, [("Tea pack", "asset-tea")], "USD")
    assert result.questions == ["appeal", "open"] and result.age_groups == ["20s"] and result.genders == ["Male"]
    unspecified = _Draft.model_validate_json(json.dumps({**GOOD, "age_groups": None, "genders": None}), strict=True)
    assert unspecified.age_groups == unspecified.genders == []
