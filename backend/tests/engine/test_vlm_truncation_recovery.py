"""Only a genuinely truncated model completion warrants a larger output budget."""

import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest
from instructor.core.exceptions import FailedAttempt, IncompleteOutputException, InstructorRetryException
from openai import AsyncOpenAI

from store_emulator.domain.config import LLMConfig
from store_emulator.engine import llm_client
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.engines.vlm_glance import VLMGlanceEngine
from store_emulator.engine.simulation.engines.vlm_glance.prompt import entry_decision_model
from tests.engine.test_llm_engine_offline import _context, _persona


async def ask(engine, stage, store):
    context = _context(store, _persona())
    if stage == "glance":
        return await engine._ask(SimpleNamespace(data_url=lambda: "data:image/png;base64,AA=="), "Look", context, store.racks[0], "E")
    return await engine._ask_plan(entry_decision_model(3), "Plan", "Visit", "data:image/png;base64,AA==" if stage == "image" else None, context)


@pytest.mark.parametrize("stage", ["text", "image", "glance"])
@pytest.mark.parametrize("kind", ["generated_phrase", "bad_request", "forbidden", "truncated_once", "always_truncated"])
def test_http_retry_budget_follows_finish_reason_not_error_text(monkeypatch, collision_store, stage, kind):
    original = llm_client.litellm.acompletion
    calls = []

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        if kind in {"bad_request", "forbidden"}:
            return httpx.Response(400 if kind == "bad_request" else 403, request=request,
                json={"error": {"type": "invalid_request_error", "message": "max_tokens exceeds this deployment's allowed output limit"}})
        if kind == "generated_phrase":
            answer = {"interest": "max_tokens length limit"} if stage == "glance" else {"enter": "max_tokens length limit"}
        else:
            answer = {"number": 0, "interest": 0} if stage == "glance" else {"enter": True, "items": []}
        finish = "length" if kind == "always_truncated" or (kind == "truncated_once" and len(calls) == 1) else "stop"
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": finish,
                "message": {"role": "assistant", "content": json.dumps(answer)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            transport = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": transport, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/local-truncation", api_base="http://127.0.0.1:8081/v1",
                structured_output="json_schema", max_tokens=160))
            from store_emulator.domain.config import SimulationConfig
            result = await ask(VLMGlanceEngine(client, AStarPathFinder(), SimulationConfig()), stage, collision_store)
            assert (result[0] is not None) == (kind == "truncated_once")
            assert bool(result[-1]) == (kind != "truncated_once")

    asyncio.run(exercise())
    budget = 160 if stage == "glance" else 410
    assert [body["max_tokens"] for body in calls] == ([budget, 2 * budget] if "truncated" in kind else [budget])


@pytest.mark.parametrize("stage", ["text", "image", "glance"])
@pytest.mark.parametrize("kind", ["direct", "wrapped", "earlier_only", "last_only"])
def test_typed_truncation_and_last_attempt_are_authoritative(collision_store, stage, kind):
    from store_emulator.domain.config import SimulationConfig

    truncation = IncompleteOutputException("response cut off")
    other = ValueError("ordinary validation failure")
    errors = {"wrapped": [truncation], "earlier_only": [truncation, other], "last_only": [other, truncation]}
    error = truncation if kind == "direct" else InstructorRetryException("failed", n_attempts=len(errors[kind]), total_usage=0,
        failed_attempts=[FailedAttempt(i + 1, exc) for i, exc in enumerate(errors[kind])])

    class Model:
        calls = 0

        async def generate_structured_async(self, schema, *args, **kwargs):
            self.calls += 1
            if self.calls == 1:
                raise error
            return schema.model_validate({})

        generate_structured_with_image_async = generate_structured_async

    model = Model()
    result = asyncio.run(ask(VLMGlanceEngine(model, AStarPathFinder(), SimulationConfig()), stage, collision_store))
    should_retry = kind != "earlier_only"
    assert model.calls == (2 if should_retry else 1)
    assert (result[0] is not None) == should_retry
