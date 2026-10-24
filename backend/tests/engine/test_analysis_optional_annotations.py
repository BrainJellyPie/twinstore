"""Valid analytical answers survive absent optional citations and follow-up text."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI
from pydantic import ValidationError

from store_emulator.domain.config import LLMConfig
from store_emulator.engine import llm_client
from store_emulator.engine.interview import ShopperReply, ask_shopper, build_journey
from store_emulator.engine.run_analyst import DifferenceReading, RunAnswer, answer_run_question, explain_difference
from tests.engine.test_interview_purchase_stops import pick, trip
from tests.engine.test_llm_impulse_exposure import fixture
from tests.engine.test_shelf_panel_boundaries import person


CASES = [("interview", field) for field in ("steps", "omitted", "valid")]
CASES += [("analyst", field) for field in ("figures", "follow_ups", "all", "omitted", "valid")]
CASES += [("comparison", field) for field in ("figures", "where", "caveats", "all", "omitted", "valid")]
FACT = "Revenue: $3.00."


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("operation,missing", CASES)
def test_answers_preserve_required_text_and_filter_citations_after_null_defaults(monkeypatch, tmp_path, mode, operation, missing):
    store, _ = fixture()
    shopper = person()
    journey = build_journey("r", trip(store, shopper.id, [pick()]), shopper, store, "USD")
    if operation == "interview":
        payload = {"answer": "I bought three teas.", "steps": [1, 999]}
        optional = ["steps"]
    elif operation == "analyst":
        payload = {"answer": "The run recorded three dollars.", "figures": [FACT, "Revenue: $999.00."],
                   "follow_ups": ["Which shelf sold the tea?"]}
        optional = ["figures", "follow_ups"]
    else:
        payload = {"summary": "Run B recorded three dollars.", "figures": [FACT, "Revenue: $999.00."],
                   "where": "The supplied totals differ.", "caveats": "The totals do not show why."}
        optional = ["figures", "where", "caveats"]
    affected = optional if missing in ("all", "omitted") else [missing] if missing != "valid" else []
    for field in affected:
        if missing == "omitted":
            payload.pop(field)
        else:
            payload[field] = None
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
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/analysis-optional-annotations", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))

            async def run():
                if operation == "interview":
                    return await ask_shopper(client, journey, store, [], "What did you buy?")
                if operation == "analyst":
                    return await answer_run_question(client, FACT, "How much was sold?", [])
                return await explain_difference(client, "Spend increased.", "Revenue: $1.00.", FACT)

            result = await run()
            data = result.model_dump()
            required = "summary" if operation == "comparison" else "answer"
            assert data[required] == payload[required]
            for field in optional:
                if field in affected:
                    assert data[field] == ([] if field in {"steps", "figures", "follow_ups"} else "")
                elif field in {"steps", "figures"}:
                    assert data[field] == ([1] if field == "steps" else [FACT])
                else:
                    assert data[field] == payload[field]
            assert (await run()).model_dump() == data and len(calls) == 1
            assert client.get_usage().cached_requests == 1

    asyncio.run(exercise())


@pytest.mark.parametrize("schema,field", [(ShopperReply, "answer"), (RunAnswer, "answer"), (DifferenceReading, "summary")])
@pytest.mark.parametrize("value", [None, "", "   ", [], 123])
def test_core_answer_is_never_invented(schema, field, value):
    with pytest.raises(ValidationError):
        schema.model_validate_json(json.dumps({field: value}), strict=True)


@pytest.mark.parametrize("schema,payload", [
    (ShopperReply, {"answer": "Valid", "steps": [None]}),
    (RunAnswer, {"answer": "Valid", "figures": "Revenue"}),
    (RunAnswer, {"answer": "Valid", "follow_ups": [123]}),
    (DifferenceReading, {"summary": "Valid", "figures": {}}),
    (DifferenceReading, {"summary": "Valid", "where": []}),
    (DifferenceReading, {"summary": "Valid", "caveats": 123}),
])
def test_malformed_non_null_annotations_remain_invalid(schema, payload):
    with pytest.raises(ValidationError):
        schema.model_validate_json(json.dumps(payload), strict=True)
