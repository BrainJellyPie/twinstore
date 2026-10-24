"""An absent explanation must not discard a respondent's valid measured choices."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI
from PIL import Image
from pydantic import ValidationError

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.marketing import ConjointAttribute
from store_emulator.domain.types import Face
from store_emulator.engine import llm_client
from store_emulator.engine.marketing import shelf_test
from store_emulator.engine.marketing.conjoint import choice_model, conjoint_panel, none_share
from store_emulator.engine.marketing.survey import likert_summary, response_model, survey_panel
from tests.engine.test_shelf_panel_boundaries import person, shelf


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("study", ["survey", "conjoint", "shelf"])
@pytest.mark.parametrize("reason", [None, "omitted", "I prefer this."])
@pytest.mark.parametrize("buys", [False, True])
def test_valid_measurements_survive_absent_reason_and_cache(monkeypatch, tmp_path, shelf, mode, study, reason, buys):
    rack, _ = shelf
    original, calls = llm_client.litellm.acompletion, []
    if study == "survey":
        payload = {"purchase_intent_A": 5 if buys else 1, "too_cheap": .5, "cheap": 1, "expensive": 2, "too_expensive": 3}
    elif study == "conjoint":
        payload = {"task_1": "B" if buys else "none"}
    else:
        payload = {"pick": 2 if buys else 0, "noticed": [2, 1]}
    if reason != "omitted":
        payload["why"] = reason

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
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/study-optional-reasons", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            with Image.new("RGB", (40, 40), "white") as board:
                async def run():
                    if study == "survey":
                        return await survey_panel(client, [person()], board, ["purchase_intent", "price_vw", "open"], 1)
                    if study == "conjoint":
                        return await conjoint_panel(client, [person()], [ConjointAttribute(name="Style", levels=["Regular", "Decaf"])],
                                                    [100, 200], product="Tea", tasks=1, options=2)
                    return await shelf_test.shelf_panel(client, [person()], rack, rack, Face.N)

                answers = await run()
                per_run = 2 if study == "shelf" else 1
                assert len(answers) == per_run and all(not answer.error for answer in answers)
                expected_reason = "I prefer this." if reason == "I prefer this." else ""
                assert all(answer.why == expected_reason for answer in answers)
                if study == "survey":
                    answer = answers[0]
                    assert answer.purchase_intent == [5 if buys else 1]
                    assert (answer.too_cheap, answer.cheap, answer.expensive, answer.too_expensive) == (50, 100, 200, 300)
                    summary = likert_summary(answer.purchase_intent, "purchase_intent", 0)
                    assert summary.n == 1 and summary.mean == (5 if buys else 1)
                elif study == "conjoint":
                    assert answers[0].tasks[0].choice == (1 if buys else None)
                    assert none_share(answers) == (0 if buys else 1)
                else:
                    assert all(answer.pick_sku == ("B" if buys else "") and answer.noticed == ["B", "A"] for answer in answers)
                    compared = shelf_test.compare_shelves(answers, "B", n_bootstrap=20)
                    pick = next(c for c in compared if c.metric == "pick")
                    assert pick.control == pick.test == int(buys) and pick.diff == 0
                assert await run() == answers
                assert len(calls) == per_run and client.get_usage().cached_requests == per_run

    asyncio.run(exercise())


@pytest.mark.parametrize("schema,payload", [
    (response_model(["purchase_intent", "open"], 1), {"purchase_intent_A": 3}),
    (choice_model(1, 2, True), {"task_1": "none"}),
    (shelf_test.ShelfAnswer, {"pick": 0}),
])
@pytest.mark.parametrize("value", [123, [], {}, "x" * 241])
def test_non_null_malformed_reason_stays_invalid(schema, payload, value):
    with pytest.raises(ValidationError):
        schema.model_validate_json(json.dumps({**payload, "why": value}), strict=True)


@pytest.mark.parametrize("schema,payload", [
    (response_model(["purchase_intent", "open"], 1), {"purchase_intent_A": None}),
    (choice_model(1, 2, True), {"task_1": None}),
    (shelf_test.ShelfAnswer, {"pick": None}),
    (shelf_test.ShelfAnswer, {"pick": 0, "noticed": None}),
])
def test_missing_measured_choices_are_never_invented(schema, payload):
    with pytest.raises(ValidationError):
        schema.model_validate_json(json.dumps({**payload, "why": None}), strict=True)
