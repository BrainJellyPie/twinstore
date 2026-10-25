"""An analyst that repeats the manager's question must retry before caching it."""

import asyncio
import json

import httpx
import pytest

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.interview import AnalystMessage
from store_emulator.engine.llm_client import LiteLLMClient
from store_emulator.engine.run_analyst import answer_run_question


@pytest.mark.parametrize("provider", ["openai", "ollama"])
@pytest.mark.parametrize("structured", ["json", "json_schema"])
@pytest.mark.parametrize("seed", [None, 0])
@pytest.mark.parametrize("kind", ["once", "current", "earlier", "punctuation", "width"])
def test_actual_sdk_retries_analyst_echoes_before_caching(monkeypatch, tmp_path, provider, structured, seed, kind):
    history = [AnalystMessage(role="user", text="Which shelf sold the most?"),
               AnalystMessage(role="analyst", text="The tea shelf.")]
    question = "How many visitors bought something?"
    echo = {"earlier": history[0].text, "punctuation": "HOW, many VISITORS bought SOMETHING!!!",
            "width": "Ｈｏｗ　ｍａｎｙ　ｖｉｓｉｔｏｒｓ　ｂｏｕｇｈｔ　ｓｏｍｅｔｈｉｎｇ？"}.get(kind, question)
    fact = "Visitors: 10. Buyers: 4 (40%)."
    good = {"answer": "Four of the ten visitors bought something.", "figures": [fact], "follow_ups": []}
    calls, recovered = [], False

    def response(request):
        if request.url.path.endswith("/api/show"):
            return httpx.Response(200, request=request, json={"model_info": {}, "capabilities": ["completion"]})
        body = json.loads(request.content)
        calls.append(body)
        data = good if recovered or kind == "once" and len(calls) > 1 else {"answer": echo, "figures": [fact]}
        content = json.dumps(data)
        if provider == "ollama":
            payload = {"model": "analyst-echo", "done": True, "done_reason": "stop",
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
    config = LLMConfig(model="ollama_chat/analyst-echo" if provider == "ollama" else "openai/analyst-echo",
        api_base="http://127.0.0.1:11434" if provider == "ollama" else "http://127.0.0.1:8081/v1",
        structured_output=structured, structured_sdk_retries=0, cache_dir=str(tmp_path), seed=seed, max_tokens=1600)

    def ask():
        return asyncio.run(answer_run_question(LiteLLMClient(config), fact, question, history, seed=9))

    if kind != "once":
        with pytest.raises(ValueError, match="repeated the question"):
            ask()
        assert len(calls) == 2 and not list(tmp_path.glob("*/*.json"))
        recovered = True
        reply = ask()
        assert len(calls) == 3
    else:
        reply = ask()
        assert len(calls) == 2
    assert reply.model_dump() == good
    assert [json.loads(p.read_text())["result"] for p in tmp_path.glob("*/*.json")] == [good]
    before = len(calls)
    assert ask().model_dump() == good and len(calls) == before
    assert "latest question" in json.dumps(calls[1]["messages"])
    assert all((b["options"]["num_predict"] if provider == "ollama" else b["max_tokens"]) == 1600 for b in calls)
    if kind == "width":
        path = next(tmp_path.glob("*/*.json"))
        path.write_text(json.dumps({"result": {"answer": echo, "figures": [fact]}}))
        assert ask().model_dump() == good and len(calls) == before + 1
