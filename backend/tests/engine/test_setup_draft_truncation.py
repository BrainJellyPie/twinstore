"""Local models can finish a cut-off store/profile draft with one bounded expansion."""

import asyncio
import json

import httpx
import pytest
from instructor.core.exceptions import FailedAttempt, IncompleteOutputException, InstructorRetryException

from store_emulator.domain.config import LLMConfig
from store_emulator.engine.generators.profile_writer import draft_profile
from store_emulator.engine.generators.store_setup_writer import draft_store_setup
from store_emulator.engine.llm_client import LiteLLMClient


def draft(model, surface):
    if surface == "profile":
        return draft_profile(model, name="동네 가게", description="동네 주민", address="서울", store_type="convenience",
                             hours="7–23", locale="ko")
    return draft_store_setup(model, "서울의 동네 주민을 위한 가게, 7시부터 23시", [("corner", "Corner Store", "convenience", "Local shop")], "ko")


@pytest.mark.parametrize("provider", ["openai", "ollama"])
@pytest.mark.parametrize("surface", ["profile", "store"])
@pytest.mark.parametrize("structured", ["json", "json_schema"])
@pytest.mark.parametrize("kind", ["once", "always", "valid", "invalid", "forbidden", "rate_limit", "then_invalid"])
def test_actual_sdk_draft_cutoff_is_bounded_and_only_valid_output_is_cached(monkeypatch, tmp_path, provider, surface, structured, kind):
    budget = 700 if surface == "profile" else 900
    answer = {"profile": "동네 주민들이 오전에는 간단한 아침거리를, 저녁에는 생활용품을 사러 옵니다."} if surface == "profile" else {
        "name": "동네 가게", "description": "동네 주민을 위한 가게입니다.", "address": "서울", "format": "Corner Store",
        "open_days": "7", "open_hour": 7, "close_hour": 23, "currency": "KRW", "rationale": "A local convenience store."}
    calls = []

    def response(request):
        if request.url.path.endswith("/api/show"):
            return httpx.Response(200, request=request, json={"model_info": {}, "capabilities": ["completion"]})
        body = json.loads(request.content)
        calls.append(body)
        if kind in {"forbidden", "rate_limit"}:
            return httpx.Response(403 if kind == "forbidden" else 429, request=request,
                json={"error": {"type": "invalid_request_error", "message": "max_tokens length limit"}})
        requested = body["options"]["num_predict"] if provider == "ollama" else body["max_tokens"]
        cutoff = kind == "always" or kind in {"once", "then_invalid"} and requested == budget
        data = {"profile": "", "open_days": "max_tokens length limit"} if kind in {"invalid", "then_invalid"} else answer
        content = json.dumps(data, ensure_ascii=False)
        if cutoff:
            content = content[:10]
        finish = "length" if cutoff else "stop"
        if provider == "ollama":
            payload = {"model": "setup-test", "done": True, "done_reason": finish,
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
    client = LiteLLMClient(LLMConfig(model=f"{'ollama_chat' if provider == 'ollama' else 'openai'}/setup-test",
        api_base="http://127.0.0.1:11434" if provider == "ollama" else "http://127.0.0.1:8081/v1",
        structured_output=structured, structured_sdk_retries=0, cache_dir=str(tmp_path), max_tokens=budget, seed=0))
    result = error = None
    try:
        result = asyncio.run(draft(client, surface))
    except Exception as exc:
        error = exc
    budgets = [b["options"]["num_predict"] if provider == "ollama" else b["max_tokens"] for b in calls]
    assert set(budgets) == ({budget, 2 * budget} if kind in {"once", "always", "then_invalid"} else {budget})
    assert budgets.count(budget) <= 2 and budgets.count(2 * budget) <= 2 and client.max_tokens == budget
    if kind in {"valid", "once"}:
        assert error is None and result is not None
        if surface == "profile":
            assert result == answer["profile"]
        else:
            assert (result.name, result.template_id, result.currency, result.open_hour, result.close_hour) == (
                answer["name"], "corner", "KRW", 7, 23)
            assert not result.warnings
        assert len(list(tmp_path.glob("*/*.json"))) == 1
    else:
        assert error is not None and result is None and not list(tmp_path.glob("*/*.json"))
    for call in calls:
        assert call["messages"][:2] == calls[0]["messages"][:2]
        assert (call["options"]["seed"] if provider == "ollama" else call["seed"]) == 0


@pytest.mark.parametrize("surface", ["profile", "store"])
@pytest.mark.parametrize("kind", ["direct", "wrapped", "earlier_only", "last_only"])
def test_only_terminal_typed_cutoff_retries_draft(surface, kind):
    cutoff, ordinary = IncompleteOutputException("cut off"), ValueError("invalid draft")
    errors = {"wrapped": [cutoff], "earlier_only": [cutoff, ordinary], "last_only": [ordinary, cutoff]}
    error = cutoff if kind == "direct" else InstructorRetryException("failed", n_attempts=len(errors[kind]),
        total_usage=0, failed_attempts=[FailedAttempt(i + 1, exc) for i, exc in enumerate(errors[kind])])

    class Model:
        def __init__(self): self.calls = []
        async def generate_structured_async(self, schema, *args, **kwargs):
            self.calls.append((args, kwargs))
            if len(self.calls) == 1:
                raise error
            return schema.model_validate({"profile": "Residents shop for their daily essentials.", "format": "Corner Store"})

    model = Model()
    if kind == "earlier_only":
        with pytest.raises(InstructorRetryException):
            asyncio.run(draft(model, surface))
    else:
        assert asyncio.run(draft(model, surface))
    budget = 700 if surface == "profile" else 900
    assert [kwargs.get("max_tokens") for _, kwargs in model.calls] == ([budget] if kind == "earlier_only" else [budget, 2 * budget])
    assert all(args == model.calls[0][0] and kwargs["seed"] == 0 and kwargs["max_retries"] == 2 for args, kwargs in model.calls)
