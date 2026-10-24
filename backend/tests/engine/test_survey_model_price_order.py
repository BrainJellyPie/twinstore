"""Inverted model price thresholds should be corrected before losing price analysis."""

import asyncio
import json
from collections import Counter

import httpx
import pytest
from openai import AsyncOpenAI
from PIL import Image

from store_emulator.application.marketing import summarize_survey
from store_emulator.domain.config import LLMConfig
from store_emulator.domain.marketing import SurveyRequest
from store_emulator.domain.types import stable_seed
from store_emulator.engine import llm_client
from store_emulator.engine.marketing.survey import response_model, survey_panel
from tests.engine.test_survey_model_price_bounds import FIELDS, PERSON


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("currency,factor", [("USD", 100), ("KRW", 1)])
@pytest.mark.parametrize("inversion", [(2, 1, 3, 4), (1, 3, 2, 4), (1, 2, 4, 3)])
@pytest.mark.parametrize("outcome", ["corrected", "repeated", "legacy_cache"])
def test_inconsistent_price_levels_do_not_become_successful_cached_answers(monkeypatch, tmp_path, mode, currency, factor, inversion, outcome):
    people = [PERSON.model_copy(update={"id": f"p{i}"}) for i in range(5)]
    by_seed = {stable_seed("survey", 0, p.id) % (2**31 - 1): p.id for p in people}
    phase = "prime" if outcome == "legacy_cache" else "invalid"
    original, calls = llm_client.litellm.acompletion, Counter()
    req = SurveyRequest(stimuli=["tea"], questions=["price_vw", "purchase_intent", "open"], currency=currency, panel=5)

    def respond(request):
        body = json.loads(request.content)
        respondent = by_seed[body["seed"]]
        calls[respondent] += 1
        bad = respondent == "p0" and phase == "invalid" and not (outcome == "corrected" and calls[respondent] > 1)
        payload = {**dict(zip(FIELDS, inversion if bad else (1, 2, 3, 4))), "purchase_intent_A": 4, "why": respondent}
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop", "message": {
                "role": "assistant", "content": json.dumps(payload)}}]})

    async def exercise():
        nonlocal phase
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/survey-price-order", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path), seed=0))
            with Image.new("RGB", (2, 2)) as board:
                async def run():
                    return await survey_panel(client, people, board, req.questions, 1, currency=currency, minor_per_major=factor)

                if outcome == "legacy_cache":
                    await run()
                    paths = list(tmp_path.rglob("*.json"))
                    assert len(paths) == 5
                    for path in paths:
                        saved = json.loads(path.read_text())
                        if saved["result"]["why"] == "p0":
                            saved["result"].update(zip(FIELDS, inversion))
                            path.write_text(json.dumps(saved))
                    phase = "invalid"
                if outcome in {"repeated", "legacy_cache"}:
                    before = calls["p0"]
                    failed = await run()
                    assert [a.respondent for a in failed if a.error] == ["p0"]
                    assert calls["p0"] == before + 2
                    partial = summarize_survey("survey", "Tea", "local", req, ["Tea"], failed)
                    assert partial.errors == 1 and partial.respondents == 4 and partial.price is None
                    if outcome == "repeated":
                        assert len(list(tmp_path.rglob("*.json"))) == 4
                    phase = "complete"
                answers = await run()
                assert all(not a.error and a.purchase_intent == [4] for a in answers)
                assert all(tuple(getattr(a, key) for key in FIELDS) == tuple(n * factor for n in (1, 2, 3, 4)) for a in answers)
                report = summarize_survey("survey", "Tea", "local", req, ["Tea"], answers)
                assert report.errors == 0 and report.respondents == 5 and report.price is not None and report.price.n == 5
                if outcome == "corrected":
                    assert calls["p0"] == 2 and sum(calls.values()) == 6
                before = calls.copy()
                assert await run() == answers and calls == before
                saved = [json.loads(path.read_text())["result"] for path in tmp_path.rglob("*.json")]
                assert len(saved) == 5 and all(tuple(row[key] for key in FIELDS) == (1, 2, 3, 4) for row in saved)

    asyncio.run(exercise())


@pytest.mark.parametrize("levels", [(0, 0, 0, 0), (1, 1, 1, 1), (0, 0, 1, 1), (1, 2, 2, 3)])
def test_equal_price_thresholds_remain_valid(levels):
    result = response_model(["price_vw"], 1).model_validate(dict(zip(FIELDS, levels)))
    assert tuple(result.model_dump()[key] for key in FIELDS) == levels


def test_non_price_questionnaires_do_not_require_price_fields():
    assert response_model(["purchase_intent"], 1).model_validate({"purchase_intent_A": 4}).model_dump() == {"purchase_intent_A": 4}
