"""An explicitly free offer is different from a survey that shows no price."""

import asyncio
import json

import httpx
import pytest
from PIL import Image

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.marketing import SurveyRequest
from store_emulator.engine.llm_client import LiteLLMClient
from store_emulator.engine.marketing.survey import survey_panel
from store_emulator.engine.marketing.survey_design import _Draft, design_survey, to_design
from store_emulator.engine.prompting import display_price
from tests.engine.test_llm_engine_offline import _persona


@pytest.mark.parametrize("provider", ["openai", "ollama"])
@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("currency", ["USD", "KRW"])
@pytest.mark.parametrize("price", [0, -0.0, None, 0.0001])
def test_actual_sdk_preserves_free_reference_through_draft_and_survey(monkeypatch, tmp_path, provider, mode, currency, price):
    payload = {"name": "Gold offer", "images": ["Gold"], "questions": ["appeal"], "reference_price": price}
    expected = 0 if price == 0 else None
    calls = []

    def response(request):
        if request.url.path.endswith("/api/show"):
            return httpx.Response(200, request=request, json={"model_info": {}, "capabilities": ["completion", "vision"]})
        body = json.loads(request.content)
        calls.append(body)
        content = json.dumps(payload if "design concept tests" in json.dumps(body["messages"]) else {"appeal_A": 4})
        if provider == "ollama":
            answer = {"model": "free-reference", "done": True, "done_reason": "stop",
                      "message": {"role": "assistant", "content": content}, "prompt_eval_count": 10, "eval_count": 5}
        else:
            answer = {"id": "offline", "object": "chat.completion", "created": 0, "model": body["model"],
                      "choices": [{"index": 0, "finish_reason": "stop",
                                   "message": {"role": "assistant", "content": content}}]}
        return httpx.Response(200, request=request, json=answer)

    def send(self, request, *args, **kwargs): return response(request)
    async def asend(self, request, *args, **kwargs): return response(request)
    monkeypatch.setattr(httpx.Client, "send", send)
    monkeypatch.setattr(httpx.AsyncClient, "send", asend)
    client = LiteLLMClient(LLMConfig(model=f"{'ollama_chat' if provider == 'ollama' else 'openai'}/free-reference",
        api_base="http://127.0.0.1:11434" if provider == "ollama" else "http://127.0.0.1:8081/v1",
        structured_output=mode, structured_sdk_retries=0, cache_dir=str(tmp_path)))

    async def exercise():
        with Image.new("RGB", (2, 2), "white") as board:
            for repeat in range(2):
                result = await design_survey(client, "Test Gold tea's free sample offer", currency, [("Gold", "gold", "Tea", "Gold tea")])
                request = SurveyRequest.model_validate(result.model_dump())
                assert request.reference_price == expected
                reference = display_price(expected, currency) if expected is not None else ""
                answers = await survey_panel(client, [_persona()], board, request.questions, 1,
                    currency=currency, reference_price=reference, minor_per_major=1 if currency == "KRW" else 100)
                assert len(answers) == 1 and not answers[0].error and answers[0].appeal == [4]
                text = json.dumps(calls[-1]["messages"], ensure_ascii=False)
                assert ("is sold for" in text) == (expected is not None)
                if expected is not None:
                    assert reference in text and not result.warnings
                assert len(calls) == 2 and client.get_usage().cached_requests == repeat * 2

    asyncio.run(exercise())


@pytest.mark.parametrize("currency", ["USD", "KRW"])
def test_unresolved_free_offer_does_not_apply_to_the_next_image(currency):
    result = to_design(_Draft(name="Free sample", images=["Missing", "Gold"], questions=["appeal"], reference_price=0),
                       [("Gold", "gold")], currency)
    assert result.stimuli == ["gold"] and result.reference_price is None
    assert any("reference price belonged to the first" in warning for warning in result.warnings)
