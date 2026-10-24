"""An open-only survey needs an actual answer, not just a successful model call."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI
from PIL import Image

from store_emulator.application.marketing import summarize_survey
from store_emulator.domain.config import LLMConfig
from store_emulator.domain.marketing import SurveyRequest
from store_emulator.engine import llm_client
from store_emulator.engine.marketing.survey import _questions_text, response_model, survey_panel
from tests.engine.test_survey_model_price_bounds import PERSON


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("value", ["omitted", None, "", " \t\u3000"])
@pytest.mark.parametrize("outcome", ["corrected", "repeated", "legacy_cache"])
def test_blank_open_answers_do_not_count_as_successful_respondents(monkeypatch, tmp_path, mode, value, outcome):
    phase = "prime" if outcome == "legacy_cache" else "invalid"
    good = {"why": "I prefer tea without sugar."}
    bad = {} if value == "omitted" else {"why": value}
    original, requests = llm_client.litellm.acompletion, []
    req = SurveyRequest(stimuli=["tea"], questions=["open"])

    def respond(request):
        body = json.loads(request.content)
        requests.append(body)
        invalid = phase == "invalid" and not (outcome == "corrected" and len(requests) > 1)
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop", "message": {
                "role": "assistant", "content": json.dumps(bad if invalid else good)}}]})

    async def exercise():
        nonlocal phase
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/survey-open-answer", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            with Image.new("RGB", (2, 2)) as board:
                async def run():
                    return await survey_panel(client, [PERSON], board, req.questions, 1)

                if outcome == "legacy_cache":
                    await run()
                    paths = list(tmp_path.rglob("*.json"))
                    assert len(paths) == 1
                    saved = json.loads(paths[0].read_text())
                    saved["result"] = bad
                    paths[0].write_text(json.dumps(saved))
                    phase = "invalid"
                if outcome in {"repeated", "legacy_cache"}:
                    before = len(requests)
                    failed = await run()
                    assert failed[0].error and not failed[0].why and len(requests) == before + 2
                    with pytest.raises(ValueError, match="No respondent could answer"):
                        summarize_survey("survey", "Tea", "local", req, ["Tea"], failed)
                    if outcome == "repeated":
                        assert not list(tmp_path.rglob("*.json"))
                    phase = "complete"
                answers = await run()
                assert not answers[0].error and answers[0].why == good["why"]
                report = summarize_survey("survey", "Tea", "local", req, ["Tea"], answers)
                assert report.respondents == 1 and report.errors == 0 and report.verbatims == [good["why"]]
                if outcome == "corrected":
                    assert len(requests) == 2
                before = len(requests)
                assert await run() == answers and len(requests) == before
                assert [json.loads(path.read_text())["result"] for path in tmp_path.rglob("*.json")] == [good]
                if mode == "json_schema":
                    schema = requests[0]["response_format"]["json_schema"]["schema"]
                    assert "why" in schema["required"] and schema["properties"]["why"]["minLength"] == 1

    asyncio.run(exercise())


@pytest.mark.parametrize("answer", ["No.", "차는 별로예요.", "  I would try it.  "])
@pytest.mark.parametrize("questions", [["open"], ["preference", "open"]])
def test_real_open_answers_need_no_positive_sentiment_or_other_measurement(answer, questions):
    result = response_model(questions, 1).model_validate({"why": answer})
    assert result.model_dump()["why"] == answer.strip()
    prompt = _questions_text(questions, 1, "USD", "")
    assert "why did you answer that way" not in prompt.lower()
    assert "what do you think" in prompt.lower()


def test_optional_explanation_remains_optional_when_a_measured_answer_exists():
    for payload in [{"purchase_intent_A": 4}, {"purchase_intent_A": 4, "why": None}]:
        result = response_model(["open", "purchase_intent"], 1).model_validate(payload)
        assert result.model_dump() == {"why": "", "purchase_intent_A": 4}
