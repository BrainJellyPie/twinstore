"""Dropping image A must not assign its shelf price to the next product."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI
from PIL import Image

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.marketing import SurveyRequest
from store_emulator.engine import llm_client
from store_emulator.engine.marketing.survey import survey_panel
from store_emulator.engine.marketing.survey_design import _Draft, design_survey, to_design
from store_emulator.engine.prompting import display_price
from tests.engine.test_llm_engine_offline import _persona


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("currency", ["USD", "KRW"])
@pytest.mark.parametrize("failure", ["missing", "ambiguous"])
@pytest.mark.parametrize("reverse", [False, True])
def test_http_missing_reference_does_not_anchor_remaining_product_survey(monkeypatch, tmp_path, mode, currency, failure, reverse):
    packages = [("Silver", "silver", "Tea Co", "Silver tea"), ("Bronze", "bronze", "Tea Co", "Bronze tea")]
    if failure == "ambiguous":
        packages += [("Gold", "gold-one", "", "Gold tea"), (" gold ", "gold-two", "", "Other gold tea")]
    if reverse:
        packages.reverse()
    original_packages = list(packages)
    payload = {"name": "Price test", "images": ["Gold", "Silver", "Bronze"],
               "questions": ["price_vw", "preference"], "reference_price": 9.99 if currency == "USD" else 9990,
               "context": "Choose a tea", "age_groups": ["20s"], "genders": ["Female"]}
    original, calls = llm_client.litellm.acompletion, []

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        design_request = "design concept tests" in json.dumps(body["messages"])
        answer = payload if design_request else dict(too_cheap=1, cheap=2, expensive=3, too_expensive=4, preferred="A")
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(answer)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/survey-reference-identity", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            with Image.new("RGB", (2, 2), "white") as board:
                for repeat in range(2):
                    design = await design_survey(client, "Compare Gold, Silver and Bronze tea prices", currency, packages)
                    request = SurveyRequest.model_validate(design.model_dump())
                    assert request.stimuli == ["silver", "bronze"] and request.stimulus_names == ["Silver", "Bronze"]
                    assert request.questions == ["price_vw", "preference"] and request.context == "Choose a tea"
                    assert request.age_groups == ["20s"] and request.genders == ["Female"]
                    reference = display_price(request.reference_price, currency) if request.reference_price is not None else ""
                    answers = await survey_panel(client, [_persona()], board, request.questions, len(request.stimuli),
                        context=request.context, currency=currency, reference_price=reference,
                        minor_per_major=1 if currency == "KRW" else 100)
                    assert len(answers) == 1 and not answers[0].error and answers[0].preferred == 0
                    survey_text = json.dumps(calls[-1]["messages"])
                    assert "it is sold for" not in survey_text
                    assert request.reference_price is None
                    assert any("reference price" in warning.lower() for warning in design.warnings)
                    assert len(calls) == 2 and client.get_usage().cached_requests == repeat * 2
                    assert packages == original_packages

    asyncio.run(exercise())


@pytest.mark.parametrize("images", [["Silver", "Missing"], [" Silver ", "Silver"], ['"Silver", brand Tea Co'], []])
def test_resolved_first_image_and_unassigned_price_drafts_keep_their_price(images):
    result = to_design(_Draft(name="Test", images=images, questions=["price_vw"], reference_price=2.49),
                       [("Silver", "silver")], "USD")
    assert result.reference_price == 249
    assert not any("reference price" in warning.lower() for warning in result.warnings)


def test_missing_first_image_without_a_price_adds_no_price_warning():
    result = to_design(_Draft(name="Test", images=["Missing", "Silver"], questions=["appeal"]),
                       [("Silver", "silver")], "USD")
    assert result.stimuli == ["silver"] and result.reference_price is None
    assert len(result.warnings) == 1 and "Missing" in result.warnings[0]
