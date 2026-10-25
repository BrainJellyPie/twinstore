"""Voting members receive the same bounded truncation recovery as single models."""

import asyncio
import json
from collections import defaultdict

import httpx
import pytest
from instructor.core.exceptions import FailedAttempt, IncompleteOutputException, InstructorRetryException
from openai import AsyncOpenAI

from store_emulator.domain.config import LLMConfig, SimulationConfig
from store_emulator.engine import llm_client
from store_emulator.engine.llm_router import EnsembleLLMClient
from store_emulator.engine.routing.pathfinder import AStarPathFinder
from store_emulator.engine.simulation.engines.vlm_glance import VLMGlanceEngine
from store_emulator.engine.simulation.engines.vlm_glance.prompt import entry_decision_model
from tests.engine.test_vlm_truncation_recovery import ask


@pytest.mark.parametrize("mode", ["json", "json_schema"])
@pytest.mark.parametrize("stage", ["text", "image", "glance"])
@pytest.mark.parametrize("kind", ["recover", "always_truncated", "generated_phrase", "bad_request", "forbidden"])
def test_http_vote_recovers_only_truncated_members_once(monkeypatch, tmp_path, collision_store, mode, stage, kind):
    original = llm_client.litellm.acompletion
    calls = defaultdict(list)
    base = 160 if stage == "glance" else 410

    def respond(request):
        body = json.loads(request.content)
        member = int(body["model"].rsplit("-", 1)[1])
        calls[member].append(body)
        if member and kind in {"bad_request", "forbidden"}:
            return httpx.Response(400 if kind == "bad_request" else 403, request=request, json={"error": {
                "type": "invalid_request_error", "message": "max_tokens exceeds this deployment's allowed output limit"}})
        if member and kind == "generated_phrase":
            payload = {"interest": "max_tokens length limit"} if stage == "glance" else {"enter": "max_tokens length limit"}
        else:
            payload = {"number": 0, "interest": 0} if stage == "glance" else {"enter": member == 0, "items": []}
        cut = member and (kind == "always_truncated" or kind == "recover" and body["max_tokens"] == base)
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "length" if cut else "stop",
                "message": {"role": "assistant", "content": json.dumps(payload)}}]})

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            adapter = AsyncOpenAI(api_key="offline", base_url="http://127.0.0.1:8081/v1", http_client=http, max_retries=0)

            async def completion(**kwargs):
                return await original(**{**kwargs, "client": adapter, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "acompletion", completion)
            clients = [llm_client.LiteLLMClient(LLMConfig(model=f"openai/vote-truncation-{i}", max_tokens=160,
                api_base="http://127.0.0.1:8081/v1", structured_output=mode, cache_dir=str(tmp_path))) for i in range(3)]
            ensemble = EnsembleLLMClient([(str(i), 1, c) for i, c in enumerate(clients)], mode="vote")
            engine = VLMGlanceEngine(ensemble, AStarPathFinder(), SimulationConfig())
            for repeat in range(2):
                result = await ask(engine, stage, collision_store)
                assert result[0] is not None and not result[-1]
                assert len(calls[0]) == 1  # Successful members are never re-asked in recovery.
                for member in (1, 2):
                    budgets = [body["max_tokens"] for body in calls[member]]
                    expected = ([base, 2 * base] + ([base] if repeat else []) if kind == "recover" else
                                [base, 2 * base] * (repeat + 1) if kind == "always_truncated" else [base] * (repeat + 1))
                    assert budgets == expected
                    assert all(body["messages"] == calls[member][0]["messages"] for body in calls[member])
                if stage != "glance":
                    assert result[0].enter is (kind != "recover")
                    assert result[2] == pytest.approx(2 / 3 if kind == "recover" else 1)
                else:
                    assert [v[2] for v in result[3]] == ([0, 0, 0] if kind == "recover" else [0, -1, -1])
            assert clients[0].get_usage().cached_requests == 1
            assert all(c.get_usage().cached_requests == int(kind == "recover") for c in clients[1:])

    asyncio.run(exercise())


@pytest.mark.parametrize("kind", ["direct", "wrapped", "earlier_only", "last_only"])
def test_member_retry_uses_only_the_terminal_typed_truncation(kind):
    truncated = IncompleteOutputException("cut off")
    other = ValueError("max_tokens length limit in invalid generated text")
    errors = {"wrapped": [truncated], "earlier_only": [truncated, other], "last_only": [other, truncated]}
    error = truncated if kind == "direct" else InstructorRetryException("failed", n_attempts=len(errors[kind]), total_usage=0,
        failed_attempts=[FailedAttempt(i + 1, e) for i, e in enumerate(errors[kind])])

    class Model:
        def __init__(self): self.calls = []
        async def generate_structured_async(self, schema, *args, **kwargs):
            self.calls.append(kwargs)
            if len(self.calls) == 1: raise error
            return schema.model_validate({"enter": True, "items": []})

    model = Model()
    ensemble = EnsembleLLMClient([("one", 1, model)], mode="vote")
    result = asyncio.run(ensemble.ask_all_with_image(entry_decision_model(3), "Plan", "Visit", None,
        max_tokens=410, retry_max_tokens=820, seed=17, route="shopper"))
    recovers = kind != "earlier_only"
    assert (result[0].answer is not None) is recovers
    assert [c["max_tokens"] for c in model.calls] == ([410, 820] if recovers else [410])
    assert all(c["seed"] == 17 and c["route"] == "shopper" for c in model.calls)


def test_generic_ensemble_calls_keep_their_existing_no_retry_default():
    class Model:
        calls = 0
        async def generate_structured_async(self, *args, **kwargs):
            self.calls += 1
            raise IncompleteOutputException("cut off")

    model = Model()
    result = asyncio.run(EnsembleLLMClient([("one", 1, model)], mode="vote").ask_all_with_image(
        entry_decision_model(3), "Plan", "Visit", None, max_tokens=410))
    assert model.calls == 1 and result[0].answer is None and result[0].error
