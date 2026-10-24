"""Optional explanations must not discard valid assistive decisions or drafts."""

import asyncio
import copy
import json

import httpx
import pytest
from openai import AsyncOpenAI
from pydantic import ValidationError

from store_emulator.domain.config import LLMConfig
from store_emulator.engine import llm_client
from store_emulator.engine.assist_router import AssistRoute, route_request
from store_emulator.engine.hypotheses import Hypothesis, suggest_tests
from store_emulator.engine.marketing.script_writer import ScriptDraft, draft_script
from store_emulator.engine.optimize.goal import _Goal, read_goal
from tests.engine.test_scenario_target_matching import target_store

CASES = {
    "route": (AssistRoute, "reason", {"destination": "optimize"}),
    "goal": (_Goal, "rationale", {"objective": "units_per_visitor", "scope": "both", "max_moves": 5,
        "keep_fridges_on_walls": True, "locked_shelves": ["Drinks 1"], "min_improvement_percent": 2}),
    "script": (ScriptDraft, "differs_by", {"name": "Value first", "script": "Tea is  $2. Would you like one?"}),
    "hypothesis": (Hypothesis, "why", {"question": "Would a sign on Cola 500ml help?", "kind": "shelf_test"}),
}


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("task", CASES)
@pytest.mark.parametrize("value", [None, "omitted", "손님의 반응을 참고했습니다."])
def test_valid_assistive_results_survive_absent_explanations_and_cache(monkeypatch, tmp_path, mode, task, value):
    _, field, data = CASES[task]
    payload = copy.deepcopy(data)
    if value != "omitted":
        payload[field] = value
    if task == "hypothesis":
        payload = {"tests": [payload]}
    original, calls = llm_client.litellm.acompletion, []
    store = target_store()
    before = store.model_dump()

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop", "message": {
                "role": "assistant", "content": json.dumps(payload)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/assist-annotations", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))

            async def run():
                if task == "route":
                    return await route_request(client, "Improve sales with at most five changes", has_run=True)
                if task == "goal":
                    return await read_goal(client, "Improve units, keep Drinks 1, at most five changes", store)
                if task == "script":
                    return await draft_script(client, product="Tea", offer="$2", context="At the shelf", facts="500 ml",
                                              current="Would you like tea?")
                return (await suggest_tests(client, "People missed the cola", store))[0]

            result = await run()
            assert getattr(result, field) == ("" if value in {None, "omitted"} else value)
            if task == "route":
                assert result.destination == "optimize"
                unavailable = await route_request(client, "Improve sales with at most five changes", has_run=False)
                assert unavailable.destination == "none"
            elif task == "goal":
                assert result.objective.value == "units_per_visitor" and result.scope.value == "both"
                assert result.max_moves == 5 and result.keep_fridges_on_walls is True
                assert result.lock_rack_ids == ["r1"] and result.min_improvement == .02 and not result.warnings
            elif task == "script":
                assert result.name == "Value first" and result.script == "Tea is $2. Would you like one?"
            else:
                assert result.question == data["question"] and result.kind == "shelf_test"
            count = len(calls)
            assert (await run()).model_dump() == result.model_dump() and len(calls) == count
            assert count == (2 if task == "route" else 1) and store.model_dump() == before
            assert client.get_usage().cached_requests == 1

    asyncio.run(exercise())


@pytest.mark.parametrize("task", CASES)
@pytest.mark.parametrize("value", [[], {}, 123, "x" * 401])
def test_non_null_malformed_explanations_remain_invalid(task, value):
    schema, field, payload = CASES[task]
    with pytest.raises(ValidationError):
        schema.model_validate({**payload, field: value})


@pytest.mark.parametrize("schema,payload", [(AssistRoute, {"destination": None}), (AssistRoute, {"destination": "unknown"}),
    (_Goal, {"locked_shelves": None}), (_Goal, {"objective": "unknown"}), (ScriptDraft, {"name": "Value", "script": None}),
    (ScriptDraft, {"name": "Value", "script": " "}), (Hypothesis, {"question": None}),
    (Hypothesis, {"question": "A real question?", "kind": "unknown"})])
def test_operational_choices_required_content_and_locks_are_not_inferred(schema, payload):
    with pytest.raises(ValidationError):
        schema.model_validate(payload)
