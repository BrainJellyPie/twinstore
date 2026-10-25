"""An echoed interview question must not become a permanently cached failure."""

import asyncio
import json

import httpx
import pytest

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.interview import InterviewMessage, Journey, JourneyStep
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
@pytest.mark.parametrize("seed", [None, 0])
@pytest.mark.parametrize("kind", ["once", "current", "earlier", "punctuation"])
def test_actual_sdk_retries_echoes_without_caching_them(monkeypatch, tmp_path, provider, surface, structured, seed, kind):
    site, shopper, session = _visit()
    store, _ = fixture()
    journey = Journey(run_id="r1", persona=_persona(), day=1, arrival_time="12:00:00", leave_time="12:01:00",
        engine_type="rule_based", currency="USD", total_spent=0, units=0, path=[],
        steps=[JourneyStep(index=1, time="12:00:00", elapsed_sec=0, action=Action.BROWSE)])
    history = [InterviewMessage(role="interviewer", text="Would a coupon have helped?"),
               InterviewMessage(role="shopper", text="Perhaps.")]
    question = "Why did you leave?"
    echo = {"earlier": "Would a coupon have helped?", "punctuation": "WHY, did you LEAVE!!!"}.get(kind, question)
    good = {"answer": "The delivery fee put me off.", "steps": [1]}
    calls = []
    recovered = False

    def response(request):
        if request.url.path.endswith("/api/show"):
            return httpx.Response(200, request=request, json={"model_info": {}, "capabilities": ["completion"]})
        body = json.loads(request.content)
        calls.append(body)
        answer = good if recovered or kind == "once" and len(calls) > 1 else {"answer": echo, "steps": []}
        content = json.dumps(answer)
        if provider == "ollama":
            payload = {"model": "echo-test", "done": True, "done_reason": "stop",
                       "message": {"role": "assistant", "content": content}, "prompt_eval_count": 10, "eval_count": 5}
        else:
            payload = {"id": "offline", "object": "chat.completion", "created": 0, "model": body["model"],
                       "choices": [{"index": 0, "finish_reason": "stop",
                                    "message": {"role": "assistant", "content": content}}]}
        return httpx.Response(200, request=request, json=payload)

    def send(self, request, *args, **kwargs): return response(request)
    async def asend(self, request, *args, **kwargs): return response(request)
    monkeypatch.setattr(httpx.Client, "send", send)
    monkeypatch.setattr(httpx.AsyncClient, "send", asend)
    config = LLMConfig(model="ollama_chat/echo-test" if provider == "ollama" else "openai/echo-test",
        api_base="http://127.0.0.1:11434" if provider == "ollama" else "http://127.0.0.1:8081/v1",
        structured_output=structured, structured_sdk_retries=0, cache_dir=str(tmp_path), seed=seed, max_tokens=700)
    client = LiteLLMClient(config)

    def ask(model):
        if surface == "physical":
            return asyncio.run(ask_store_shopper(model, journey, store, history, question))
        return asyncio.run(ask_shopper(model, site, shopper, session, history, question, run_id="r1"))

    if kind != "once":
        with pytest.raises(ValueError, match="repeated the question"):
            ask(client)
        assert len(calls) == 2
        recovered = True
        # The app creates a new client when the user retries the failed question.
        reply = ask(LiteLLMClient(config))
        assert len(calls) == 3
    else:
        reply = ask(client)
        assert len(calls) == 2
    assert reply.model_dump() == good
    assert [json.loads(p.read_text())["result"] for p in tmp_path.glob("*/*.json")] == [good]
    before = len(calls)
    assert ask(LiteLLMClient(config)).model_dump() == good and len(calls) == before
    assert all((b["options"]["num_predict"] if provider == "ollama" else b["max_tokens"]) == 700 for b in calls)
    assert "first-person voice" in json.dumps(calls[1]["messages"])
    if kind == "punctuation":
        path = next(tmp_path.glob("*/*.json"))
        path.write_text(json.dumps({"result": {"answer": echo, "steps": []}}))
        assert ask(LiteLLMClient(config)).model_dump() == good and len(calls) == before + 1
