"""Changing the shown price must reach respondents and invalidate cached survey answers."""

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
from store_emulator.engine.marketing.survey import SCALES, survey_panel
from store_emulator.engine.prompting import display_price
from tests.engine.test_llm_engine_offline import _persona


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("currency", ["USD", "KRW"])
@pytest.mark.parametrize("questions", [["value"], ["purchase_intent"], ["preference"], ["open"],
                                      ["price_vw"], ["value", "price_vw", "open"]])
def test_http_reference_price_changes_answers_and_cache_for_every_questionnaire(monkeypatch, tmp_path, mode, currency, questions):
    prices = [199, 999, 0, None] if currency == "USD" else [1990, 9990, 0, None]
    references = [display_price(price, currency) if price is not None else "" for price in prices]
    expected_scores = [4, 1, 5, 3]
    original, calls, shown_prices = llm_client.litellm.acompletion, [], []

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        text = json.dumps(body["messages"], ensure_ascii=False)
        shown = next((price for price in references[:-1] if f"sold for {price}" in text), "")
        if shown:
            assert (f"Product A is sold for {shown}." in text
                    or f"For product A, in {currency} (it is sold for {shown})" in text)
            assert text.count(f"sold for {shown}") == 1
        shown_prices.append(shown)
        score = expected_scores[references.index(shown)]
        payload = {}
        for question in questions:
            if question in SCALES:
                payload.update({f"{question}_A": score, f"{question}_B": 3})
            elif question == "preference":
                payload["preferred"] = "A" if score >= 3 else "B"
            elif question == "open":
                payload["why"] = f"Value score {score} for product A."
            elif question == "price_vw":
                payload.update(too_cheap=score, cheap=score + 1, expensive=score + 2, too_expensive=score + 3)
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(payload)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/survey-price-context", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            persona = _persona()
            before = persona.model_dump_json()
            minor = 1 if currency == "KRW" else 100
            with Image.new("RGB", (2, 2), "white") as board:
                runs = []
                for repeat in range(2):
                    current = []
                    for reference in references:
                        answers = await survey_panel(client, [persona], board, questions, 2, context="Compare these teas",
                            currency=currency, reference_price=reference, minor_per_major=minor)
                        assert len(answers) == 1 and not answers[0].error
                        current.append(answers)
                    runs.append(current)
                    assert len(calls) == 4 and shown_prices == references
                    assert client.get_usage().cached_requests == repeat * 4
                assert runs[0] == runs[1] and persona.model_dump_json() == before
                for price, score, answers in zip(prices, expected_scores, runs[0], strict=True):
                    request = SurveyRequest(stimuli=["tea", "other"], questions=questions, currency=currency,
                                            reference_price=price)
                    report = summarize_survey("survey", "Price test", "offline", request, ["Tea", "Other"], answers)
                    for scale in report.scales:
                        assert scale.mean == (score if scale.stimulus == 0 else 3)
                    if "preference" in questions:
                        assert answers[0].preferred == (0 if score >= 3 else 1)
                    if "open" in questions:
                        assert answers[0].why == f"Value score {score} for product A."
                    if "price_vw" in questions:
                        assert answers[0].too_cheap == score * minor

    asyncio.run(exercise())
