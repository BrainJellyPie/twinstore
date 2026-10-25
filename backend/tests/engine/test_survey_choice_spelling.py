"""Unambiguous preference labels should not discard the rest of a valid questionnaire."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI
from PIL import Image
from pydantic import ValidationError

from store_emulator.application.marketing import summarize_survey
from store_emulator.domain.config import LLMConfig
from store_emulator.domain.marketing import SurveyRequest
from store_emulator.engine import llm_client
from store_emulator.engine.marketing.survey import LETTERS, response_model, survey_panel
from tests.engine.test_survey_model_price_bounds import PERSON


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("count,letter", [(n, c) for n in (2, 3, 4) for c in LETTERS[:n]])
@pytest.mark.parametrize("padded", [False, True])
def test_choice_spelling_preserves_ratings_report_counts_and_cache(monkeypatch, tmp_path, mode, count, letter, padded):
    said = f"\u3000{letter.lower()}\t" if padded else letter.lower()
    payload = {"preferred": said, "why": None, **{f"appeal_{c}": i + 1 for i, c in enumerate(LETTERS[:count])}}
    original, calls = llm_client.litellm.acompletion, []
    names = [f"Tea {c}" for c in LETTERS[:count]]
    req = SurveyRequest(stimuli=[f"tea_{c}" for c in LETTERS[:count]], questions=["preference", "appeal", "open"])

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
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/survey-choice", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            with Image.new("RGB", (2, 2)) as board:
                answers = await survey_panel(client, [PERSON], board, req.questions, count)
                assert not answers[0].error and answers[0].preferred == LETTERS.index(letter)
                assert answers[0].appeal == list(range(1, count + 1)) and answers[0].why == ""
                report = summarize_survey("survey", "Tea", "local", req, names, answers)
                assert report.respondents == 1 and report.errors == 0
                assert [p.share for p in report.preference] == [int(c == letter) for c in LETTERS[:count]]
                assert len(calls) == 1
                path = next(tmp_path.rglob("*.json"))
                saved = json.loads(path.read_text())
                assert saved["result"]["preferred"] == letter
                saved["result"]["preferred"] = said
                path.write_text(json.dumps(saved))
                assert await survey_panel(client, [PERSON], board, req.questions, count) == answers
                assert len(calls) == 1 and client.get_usage().cached_requests == 1

    asyncio.run(exercise())


@pytest.mark.parametrize("value", ["", " ", None, "C", "c", "AB", "A/B", "Option A", 0, []])
def test_missing_or_ambiguous_or_unoffered_choices_remain_invalid(value):
    schema = response_model(["preference"], 2)
    with pytest.raises(ValidationError):
        schema.model_validate({"preferred": value})
    with pytest.raises(ValidationError):
        schema.model_validate({})


def test_choice_schema_keeps_canonical_required_values_and_single_image_has_no_choice():
    for count in (2, 3, 4):
        schema = response_model(["preference"], count).model_json_schema()
        assert schema["properties"]["preferred"]["enum"] == list(LETTERS[:count])
        assert "preferred" in schema["required"]
    single = response_model(["preference", "open"], 1)
    assert single.model_validate({"why": "I like it.", "preferred": "a"}).model_dump() == {"why": "I like it."}
