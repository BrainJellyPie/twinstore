"""Local interview answers recover a terminal output cutoff within a fixed budget."""

import asyncio
import json

import httpx
import pytest
from instructor.core.exceptions import FailedAttempt, IncompleteOutputException, InstructorRetryException

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.interview import Journey, JourneyStep
from store_emulator.domain.types import Action
from store_emulator.engine.interview import ask_shopper as ask_store_shopper
from store_emulator.engine.llm_client import LiteLLMClient
from store_emulator.engine.online.interview import ask_shopper
from tests.engine.test_online_interview import _visit
from tests.engine.test_llm_engine_offline import _persona
from tests.engine.test_llm_impulse_exposure import fixture


@pytest.mark.parametrize("provider", ["openai", "ollama"])
@pytest.mark.parametrize("surface", ["online", "physical"])
@pytest.mark.parametrize("structured", ["json", "json_schema"])
@pytest.mark.parametrize("kind", ["truncated_once", "always_truncated", "generated_phrase", "valid",
                                 "bad_request", "forbidden", "rate_limit", "truncated_then_echo"])
def test_actual_sdk_interview_cutoff_recovery(monkeypatch, tmp_path, provider, surface, structured, kind):
    site, shopper, session = _visit()
    store, _ = fixture()
    journey = Journey(run_id="r1", persona=_persona(), day=1, arrival_time="12:00:00", leave_time="12:01:00",
        engine_type="rule_based", currency="USD", total_spent=0, units=0, path=[],
        steps=[JourneyStep(index=1, time="12:00:00", elapsed_sec=0, action=Action.BROWSE)])
    answer = {"answer": "The delivery fee made me leave.", "steps": [1]}
    calls = []

    def response(request):
        if request.url.path.endswith("/api/show"):
            return httpx.Response(200, request=request, json={"model_info": {}, "capabilities": ["completion"]})
        body = json.loads(request.content)
        calls.append(body)
        if kind in {"bad_request", "forbidden", "rate_limit"}:
            return httpx.Response({"bad_request": 400, "forbidden": 403, "rate_limit": 429}[kind], request=request,
                json={"error": {"type": "invalid_request_error", "message": "max_tokens length limit"}})
        budget = body["options"]["num_predict"] if provider == "ollama" else body["max_tokens"]
        cutoff = kind == "always_truncated" or kind in {"truncated_once", "truncated_then_echo"} and budget == 700
        content = json.dumps(answer)[:10] if cutoff else json.dumps(answer)
        if kind == "truncated_then_echo" and not cutoff:
            content = json.dumps({"answer": "Why did you leave?", "steps": []})
        if kind == "generated_phrase":
            content = json.dumps({"answer": "max_tokens length limit", "steps": ["max_tokens length limit"]})
        finish = "length" if cutoff else "stop"
        if provider == "ollama":
            payload = {"model": "interview-test", "done": True, "done_reason": finish,
                       "message": {"role": "assistant", "content": content}, "prompt_eval_count": 10, "eval_count": 5}
        else:
            payload = {"id": "offline", "object": "chat.completion", "created": 0, "model": body["model"],
                       "choices": [{"index": 0, "finish_reason": finish,
                                    "message": {"role": "assistant", "content": content}}]}
        return httpx.Response(200, request=request, json=payload)

    def send(self, request, *args, **kwargs): return response(request)
    async def asend(self, request, *args, **kwargs): return response(request)
    monkeypatch.setattr(httpx.Client, "send", send)
    monkeypatch.setattr(httpx.AsyncClient, "send", asend)
    client = LiteLLMClient(LLMConfig(model="ollama_chat/interview-test" if provider == "ollama" else "openai/interview-test",
        api_base="http://127.0.0.1:11434" if provider == "ollama" else "http://127.0.0.1:8081/v1",
        structured_output=structured, structured_sdk_retries=0, cache_dir=str(tmp_path), max_tokens=700, seed=0))
    reply = error = None
    try:
        reply = asyncio.run(ask_store_shopper(client, journey, store, [], "Why did you leave?") if surface == "physical"
                            else ask_shopper(client, site, shopper, session, [], "Why did you leave?", run_id="r1"))
    except Exception as exc:
        error = exc
    budgets = [b["options"]["num_predict"] if provider == "ollama" else b["max_tokens"] for b in calls]
    assert budgets and budgets[0] == 700 and client.max_tokens == 700
    assert set(budgets) == ({700, 1400} if "truncated" in kind else {700})
    assert budgets.count(700) <= 2 and budgets.count(1400) <= 2
    if kind in {"truncated_once", "valid"}:
        assert error is None and reply is not None and reply.model_dump() == answer
        assert [json.loads(p.read_text())["result"] for p in tmp_path.glob("*/*.json")] == [answer]
    else:
        assert reply is None and error is not None
        assert not list(tmp_path.glob("*/*.json"))
        if kind == "truncated_then_echo":
            assert isinstance(error, ValueError) and "repeated the question" in str(error)
    for call in calls:
        assert call["messages"][:2] == calls[0]["messages"][:2]
        key = "options" if provider == "ollama" else None
        assert (call[key]["seed"] if key else call["seed"]) == (
            calls[0][key]["seed"] if key else calls[0]["seed"])


@pytest.mark.parametrize("kind", ["direct", "wrapped", "earlier_only", "last_only"])
@pytest.mark.parametrize("surface", ["online", "physical"])
def test_only_the_terminal_cutoff_expands_the_interview_budget(kind, surface):
    site, shopper, session = _visit()
    store, _ = fixture()
    journey = Journey(run_id="r1", persona=_persona(), day=1, arrival_time="12:00:00", leave_time="12:01:00",
        engine_type="rule_based", currency="USD", total_spent=0, units=0, path=[],
        steps=[JourneyStep(index=1, time="12:00:00", elapsed_sec=0, action=Action.BROWSE)])
    cutoff, ordinary = IncompleteOutputException("cut off"), ValueError("invalid answer")
    errors = {"wrapped": [cutoff], "earlier_only": [cutoff, ordinary], "last_only": [ordinary, cutoff]}
    error = cutoff if kind == "direct" else InstructorRetryException("failed", n_attempts=len(errors[kind]),
        total_usage=0, failed_attempts=[FailedAttempt(i + 1, exc) for i, exc in enumerate(errors[kind])])

    class Model:
        calls = []

        async def generate_structured_async(self, schema, *args, **kwargs):
            self.calls.append((args, kwargs))
            if len(self.calls) == 1:
                raise error
            return schema.model_validate({"answer": "I was browsing.", "steps": [1]})

    model = Model()
    request = (ask_store_shopper(model, journey, store, [], "Why?") if surface == "physical"
               else ask_shopper(model, site, shopper, session, [], "Why?", run_id="r1"))
    if kind == "earlier_only":
        with pytest.raises(InstructorRetryException):
            asyncio.run(request)
    else:
        reply = asyncio.run(request)
        assert reply.answer == "I was browsing."
    assert [call[1].get("max_tokens") for call in model.calls] == ([700] if kind == "earlier_only" else [700, 1400])
    assert all(call[0] == model.calls[0][0] and call[1]["seed"] == model.calls[0][1]["seed"]
               and call[1]["max_retries"] == 2 for call in model.calls)
