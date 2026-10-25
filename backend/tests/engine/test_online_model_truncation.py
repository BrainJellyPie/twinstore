"""A cut-off online shopper decision gets one bounded chance to complete."""

import asyncio
import json
import random

import httpx
import pytest
from instructor.core.exceptions import FailedAttempt, IncompleteOutputException, InstructorRetryException

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.online import ActionKind, BrowserState, ExitSurvey
from store_emulator.engine.llm_client import LiteLLMClient
from store_emulator.engine.online.browser import build_page, numbering, outline
from store_emulator.engine.online.policies import Memory, ModelPolicy, StepView
from tests.engine.test_online_store import _shoppers, _site


@pytest.mark.parametrize("provider", ["openai", "ollama"])
@pytest.mark.parametrize("operation", ["choice", "survey"])
@pytest.mark.parametrize("vision", [False, True])
@pytest.mark.parametrize("structured", ["json", "json_schema"])
@pytest.mark.parametrize("kind", ["truncated_once", "always_truncated", "generated_phrase", "valid",
                                 "bad_request", "forbidden", "rate_limit"])
def test_actual_sdk_recovers_only_a_typed_cutoff(monkeypatch, tmp_path, provider, operation, vision, structured, kind):
    site = _site(welcome_popup="none")
    shopper = _shoppers(site, 1)[0]
    state = BrowserState()
    page = build_page(site, state)
    numbers = numbering(page, 37)
    view = StepView(page, state, numbers, outline(page, site), image_url="data:image/png;base64,AA==", seed=123)
    search = page.header.search
    assert search is not None
    answer = {"option": numbers[search.index], "search_text": "green tea", "thought": "Find my usual tea."}
    if operation == "survey":
        answer = {"satisfaction": 2, "ease": 3, "recommend": 1, "would_return": False,
                  "frustration": "I could not find what I wanted.", "improvement": "Improve the search results."}
    calls = []

    def response(request):
        if request.url.path.endswith("/api/show"):
            return httpx.Response(200, request=request, json={"model_info": {}, "capabilities": ["completion", "vision"]})
        body = json.loads(request.content)
        calls.append(body)
        if kind in {"bad_request", "forbidden", "rate_limit"}:
            return httpx.Response({"bad_request": 400, "forbidden": 403, "rate_limit": 429}[kind], request=request,
                json={"error": {"type": "invalid_request_error", "message": "max_tokens length limit"}})
        budget = body["options"]["num_predict"] if provider == "ollama" else body["max_tokens"]
        cutoff = kind == "always_truncated" or kind == "truncated_once" and budget == 240
        content = json.dumps(answer)[:10] if cutoff else json.dumps(answer)
        if kind == "generated_phrase":
            content = json.dumps({"option" if operation == "choice" else "satisfaction": "max_tokens length limit"})
        finish = "length" if cutoff else "stop"
        if provider == "ollama":
            payload = {"model": "online-test", "done": True, "done_reason": finish,
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
    client = LiteLLMClient(LLMConfig(model="ollama_chat/online-test" if provider == "ollama" else "openai/online-test",
        api_base="http://127.0.0.1:11434" if provider == "ollama" else "http://127.0.0.1:8081/v1",
        structured_output=structured, structured_sdk_retries=0, cache_dir=str(tmp_path), max_tokens=900,
        seed=0))
    original = state.model_dump()
    policy = ModelPolicy(client, vision=vision)
    result = asyncio.run(policy.choose(site, shopper, view, Memory(), random.Random(7)) if operation == "choice"
                         else policy.survey(site, shopper, history=["Home: searched for tea", "Search: left"],
                                            outcome="left", seconds=30, paid=0, seed=123))
    budgets = [b["options"]["num_predict"] if provider == "ollama" else b["max_tokens"] for b in calls]
    assert budgets == ([240, 480] if "truncated" in kind else [240])
    assert client.max_tokens == 900 and state.model_dump() == original
    if kind in {"truncated_once", "valid"}:
        if operation == "choice":
            assert result.source == "model" and result.control.action.kind == ActionKind.SEARCH
            assert result.query == "green tea" and result.thought == answer["thought"] and not result.error
        else:
            assert result == ExitSurvey.model_validate(answer)
        cached = [json.loads(p.read_text())["result"] for p in tmp_path.glob("*/*.json")]
        assert cached == [answer]
    else:
        if operation == "choice":
            assert result.source == "fallback" and result.error and result.control in page.active
        else:
            assert result is None
        assert not list(tmp_path.glob("*/*.json"))
    if len(calls) == 2:
        assert calls[0]["messages"] == calls[1]["messages"]
        if provider == "ollama":
            assert calls[0]["options"]["seed"] == calls[1]["options"]["seed"] == 123
        else:
            assert calls[0]["seed"] == calls[1]["seed"] == 123


@pytest.mark.parametrize("vision", [False, True])
@pytest.mark.parametrize("kind", ["direct", "wrapped", "earlier_only", "last_only"])
@pytest.mark.parametrize("operation", ["choice", "survey"])
def test_only_the_terminal_typed_error_can_increase_the_budget(vision, kind, operation):
    site = _site(welcome_popup="none")
    shopper = _shoppers(site, 1)[0]
    state = BrowserState()
    page = build_page(site, state)
    numbers = numbering(page, 41)
    view = StepView(page, state, numbers, outline(page, site), image_url="data:image/png;base64,AA==", seed=17)
    truncation = IncompleteOutputException("response cut off")
    ordinary = ValueError("ordinary validation failure")
    errors = {"wrapped": [truncation], "earlier_only": [truncation, ordinary], "last_only": [ordinary, truncation]}
    error = truncation if kind == "direct" else InstructorRetryException("failed", n_attempts=len(errors[kind]),
        total_usage=0, failed_attempts=[FailedAttempt(i + 1, exc) for i, exc in enumerate(errors[kind])])

    class Model:
        calls = []

        async def generate_structured_async(self, schema, *args, **kwargs):
            self.calls.append(kwargs)
            if len(self.calls) == 1:
                raise error
            return schema.model_validate({"option": numbers[page.leave.index]} if operation == "choice" else {
                "satisfaction": 4, "ease": 5, "recommend": 6, "would_return": True,
            })

        generate_structured_with_image_async = generate_structured_async

    model = Model()
    policy = ModelPolicy(model, vision=vision, max_tokens=160)
    result = asyncio.run(policy.choose(site, shopper, view, Memory(), random.Random(7)) if operation == "choice"
                         else policy.survey(site, shopper, history=[], outcome="left", seconds=30, paid=0, seed=17))
    should_retry = kind != "earlier_only"
    assert [c["max_tokens"] for c in model.calls] == ([160, 320] if should_retry else [160])
    if operation == "choice":
        assert result.source == ("model" if should_retry else "fallback")
    else:
        assert (result is not None) == should_retry
    assert all(c["route"] == shopper.id and c["seed"] == 17 for c in model.calls)
