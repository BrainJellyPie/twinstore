"""Known model choices retain tool availability and optimizer/test semantics."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI
from pydantic import ValidationError

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.optimize import OptimizeConstraints, OptimizeObjective, OptimizeScope, OptimizeSpec
from store_emulator.engine import llm_client
from store_emulator.engine.assist_router import AssistRoute, route_request
from store_emulator.engine.hypotheses import Hypothesis, suggest_tests
from store_emulator.engine.optimize.goal import _Goal, read_goal
from tests.engine.test_scenario_target_matching import target_store

CHOICES = {
    "route": ("ab_test", "shelf_test", "conjoint", "concept_test", "staff_script", "layout_edit", "area",
              "run_question", "find_shoppers", "optimize", "none"),
    "objective": tuple(OptimizeObjective), "scope": tuple(OptimizeScope),
    "hypothesis": ("ab_test", "shelf_test", "concept_test"),
}


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("task,value", [(task, value) for task, values in CHOICES.items() for value in values])
def test_http_known_choices_preserve_tool_rules_and_settings(monkeypatch, tmp_path, mode, task, value):
    said = f"\u3000{value.upper()}\t"
    payload = ({"destination": said, "reason": "Keep Reason"} if task == "route" else
               {"tests": [{"kind": said, "question": "Does the Tea sign help?", "why": "Keep Evidence"}]} if task == "hypothesis" else
               {"objective": "units_per_visitor", "scope": "both", task: said, "max_moves": 5,
                "keep_fridges_on_walls": True, "locked_shelves": ["Drinks 1"], "min_improvement_percent": 2,
                "rationale": "Keep Goal"})
    store = target_store()
    before = store.model_dump()
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
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/assist-choice-spelling", api_base="http://127.0.0.1:8081/v1",
                structured_output=mode, cache_dir=str(tmp_path)))
            for repeat in range(2):
                if task == "route":
                    for has_run in (True, False):
                        result = await route_request(client, "Help with this store", has_run=has_run)
                        expected = "none" if not has_run and value in {"run_question", "find_shoppers", "optimize"} else value
                        assert result.destination == expected and result.reason == "Keep Reason"
                elif task == "hypothesis":
                    result = await suggest_tests(client, "People missed the tea sign", store)
                    assert len(result) == 1 and result[0].kind == value and result[0].question == "Does the Tea sign help?"
                    assert result[0].why == "Keep Evidence"
                else:
                    result = await read_goal(client, "Keep Drinks 1 fixed; at most five moves and at least 2 percent gain", store)
                    assert result.objective == (value if task == "objective" else "units_per_visitor")
                    assert result.scope == (value if task == "scope" else "both")
                    assert result.lock_rack_ids == ["r1"] and result.max_moves == 5 and result.min_improvement == .02
                    assert result.keep_fridges_on_walls is True and result.rationale == "Keep Goal" and not result.warnings
                    spec = OptimizeSpec(objective=result.objective, scope=result.scope, constraints=OptimizeConstraints(
                        max_moves=result.max_moves, lock_rack_ids=result.lock_rack_ids, min_improvement=result.min_improvement))
                    assert spec.objective.maximize is (spec.objective != OptimizeObjective.WALKING_DISTANCE)
                count = 2 if task == "route" else 1
                assert len(calls) == count and client.get_usage().cached_requests == count * repeat
                assert store.model_dump() == before

    asyncio.run(exercise())


@pytest.mark.parametrize("schema,field,payload", [(AssistRoute, "destination", {}), (_Goal, "objective", {}),
    (_Goal, "scope", {}), (Hypothesis, "kind", {"question": "Does a Tea sign help?"})])
@pytest.mark.parametrize("value", [None, "", "unknown", "ab test", "walking distance", 1, True, [], {}])
def test_unlisted_choices_internal_spaces_and_wrong_types_still_fail(schema, field, payload, value):
    with pytest.raises(ValidationError):
        schema.model_validate_json(json.dumps({**payload, field: value}), strict=True)
