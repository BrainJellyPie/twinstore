"""Native Ollama cutoffs must survive SDK translation and reach bounded recovery."""

import asyncio
import hashlib
import json
import re

import httpx
import pytest
from instructor.core.exceptions import IncompleteOutputException, InstructorRetryException
from pydantic import BaseModel

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.types import Weekday
from store_emulator.engine.generators import persona as gen
from store_emulator.engine.llm_client import LiteLLMClient
from tests.engine.test_customer_truncated_batches import hourly, profile


class Reply(BaseModel):
    text: str


@pytest.fixture
def native_transport(monkeypatch):
    def install(respond):
        def response(request):
            if request.url.path.endswith("/api/show"):
                return httpx.Response(200, request=request, json={"model_info": {}, "capabilities": ["completion", "vision"]})
            content, reason = respond(json.loads(request.content))
            return httpx.Response(200, request=request, json={"model": "local-finish-reason", "done": True,
                "done_reason": reason, "message": {"role": "assistant", "content": content},
                "prompt_eval_count": 10, "eval_count": 5})
        def send(self, request, *args, **kwargs): return response(request)
        async def asend(self, request, *args, **kwargs): return response(request)
        monkeypatch.setattr(httpx.Client, "send", send)
        monkeypatch.setattr(httpx.AsyncClient, "send", asend)
    return install


@pytest.mark.parametrize("mode", ["sync", "sync_image", "async", "async_image"])
@pytest.mark.parametrize("structured", ["json", "json_schema"])
@pytest.mark.parametrize("reason,content", [("length", '{"text":"partial"}'), ("length", '{"text":'),
    ("stop", '{"text":"ready"}'), (None, '{"text":"ready"}'), ("", '{"text":"ready"}')])
def test_native_cutoffs_are_not_accepted_or_cached(native_transport, tmp_path, mode, structured, reason, content):
    calls = []
    def respond(body):
        calls.append(body)
        return content, reason
    native_transport(respond)
    client = LiteLLMClient(LLMConfig(model="ollama_chat/local-finish-reason", api_base="http://127.0.0.1:11434",
        structured_output=structured, cache_dir=str(tmp_path)))
    def ask():
        args = (Reply, "Reply in JSON.", "Hello")
        if mode == "sync": return client.generate_structured(*args, max_retries=2)
        if mode == "sync_image": return client.generate_structured_with_image(*args, "data:image/png;base64,AA==", max_retries=2)
        if mode == "async": return asyncio.run(client.generate_structured_async(*args, max_retries=2))
        return asyncio.run(client.generate_structured_with_image_async(*args, "data:image/png;base64,AA==", max_retries=2))
    if reason == "length":
        with pytest.raises(InstructorRetryException) as caught:
            ask()
        assert isinstance(caught.value.failed_attempts[-1].exception, IncompleteOutputException)
        assert len(calls) == 2 and not list(tmp_path.glob("*/*.json"))
        assert client.get_usage().requests == 2 and client.get_usage().total_tokens == 30
    else:
        assert ask().text == ask().text == "ready"
        assert len(calls) == 1 and client.get_usage().cached_requests == 1


@pytest.mark.parametrize("count", [4, 5, 12])
def test_native_customer_cutoff_recovers_without_missing_visits(native_transport, tmp_path, count):
    calls = []
    def respond(body):
        prompt = next(m["content"] for m in body["messages"] if m["role"] == "user" and "페르소나" in m["content"])
        hours = [int(h) for h in re.findall(r"^\[\d+\] (\d+)시", prompt, re.MULTILINE)]
        calls.append(len(hours))
        if len(hours) == count:
            return '{"personas":[', "length"
        return json.dumps({"personas": [gen.GeneratedPersona(identity="resident", age_group="30s", gender="Female",
            description=f"Arrived at {h}", intent="Buy groceries", purpose="groceries").model_dump() for h in hours]}), "stop"
    native_transport(respond)
    client = LiteLLMClient(LLMConfig(model="ollama_chat/local-finish-reason", api_base="http://127.0.0.1:11434",
        structured_output="json_schema", cache_dir=str(tmp_path)))
    async def exercise():
        first = await gen.generate_personas_for_day(client, "offline", profile(), Weekday.MON, hourly(count), batch_size=count, seed=42)
        second = await gen.generate_personas_for_day(client, "offline", profile(), Weekday.MON, hourly(count), batch_size=count, seed=42)
        assert first == second and [p.arrival_hour for p in first] == list(range(9, 9 + count))
        assert [p.description for p in first] == [f"Arrived at {h}" for h in range(9, 9 + count)]
    asyncio.run(exercise())
    assert calls == [count, count, count, count // 2, count - count // 2, count, count, count]
    assert client.get_usage().cached_requests == 2 and client.get_usage().total_tokens == 120
    entries = [json.loads(p.read_text())["result"] for p in tmp_path.glob("*/*.json")]
    assert sorted(len(entry["personas"]) for entry in entries) == [count // 2, count - count // 2]


def test_answers_cached_before_native_cutoff_validation_are_not_reused(tmp_path):
    client = LiteLLMClient(LLMConfig(model="ollama_chat/local-finish-reason", api_base="http://127.0.0.1:11434", cache_dir=str(tmp_path)))
    messages = [{"role": "user", "content": "Hello"}]
    old_key = hashlib.sha256(json.dumps({"structured_parser": "final-think-v2", "model": client.model,
        "api_base": client.api_base, "temperature": client.temperature, "max_tokens": client.max_tokens,
        "seed": client._effective_seed(None), "schema": Reply.model_json_schema(), "messages": messages},
        sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    old_path = tmp_path / old_key[:2] / f"{old_key}.json"
    client._cache_put(old_path, Reply(text="partial"))
    assert client._cache_get(client._cache_path(Reply, messages, None), Reply) is None
    assert old_path.exists()
