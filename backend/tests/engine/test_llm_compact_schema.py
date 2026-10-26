"""Local JSON requests preserve the complete schema without its whitespace overhead."""

import asyncio
import hashlib
import json

import httpx
import pytest
from pydantic import BaseModel, Field, SecretStr

from store_emulator.domain.config import LLMConfig
from store_emulator.engine.llm_client import LiteLLMClient
from store_emulator.engine.online.design_chat import DesignReply


class Answer(DesignReply):
    reply: str = Field(description="고객의 답변; preserve  double spaces", max_length=120)


class SmallAnswer(BaseModel):
    reply: str


def config(path, mode, base):
    return LLMConfig(model="openai/compact-schema", api_base=base, api_key=SecretStr("offline"),
        structured_output=mode, cache_dir=str(path), temperature=0, seed=None,
        max_tokens=160, structured_sdk_retries=0)


def responses(monkeypatch, *, invalid_first=False):
    seen = []

    def respond(request):
        body = json.loads(request.content)
        seen.append(body)
        content = {} if invalid_first and len(seen) == 1 else {"updates": [], "reply": "ready"}
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion",
            "created": 0, "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
            "message": {"role": "assistant", "content": json.dumps(content)}}]})

    def send(self, request, *args, **kwargs):
        return respond(request)

    async def asend(self, request, *args, **kwargs):
        return respond(request)

    monkeypatch.setattr(httpx.Client, "send", send)
    monkeypatch.setattr(httpx.AsyncClient, "send", asend)
    return seen


async def ask(client, method, system, user):
    args = (Answer, system, user)
    if method.endswith("image"):
        args += ("data:image/png;base64,AA==",)
    if method == "sync_text":
        return client.generate_structured(*args, max_retries=2)
    if method == "sync_image":
        return client.generate_structured_with_image(*args, max_retries=2)
    if method == "async_text":
        return await client.generate_structured_async(*args, max_retries=2)
    return await client.generate_structured_with_image_async(*args, max_retries=2)


@pytest.mark.parametrize("method", ["sync_text", "async_text", "sync_image", "async_image"])
@pytest.mark.parametrize("mode,base,compact", [
    ("json", "http://127.0.0.1:8081/v1", True),
    ("json", "http://model.example.invalid/v1", False),
    ("json_schema", "http://127.0.0.1:8081/v1", False),
])
def test_wire_schema_retry_user_content_and_image_are_preserved(tmp_path, monkeypatch, method, mode, base, compact):
    seen = responses(monkeypatch, invalid_first=True)
    client = LiteLLMClient(config(tmp_path, mode, base))
    schema = Answer.model_json_schema()
    pretty = json.dumps(schema, indent=2, ensure_ascii=False)
    minified = json.dumps(schema, separators=(",", ":"), ensure_ascii=False)
    system = "Answer the question. Preserve  spaces and\nline breaks."
    user = "Explain this example verbatim:\n" + pretty

    async def exercise():
        assert (await ask(client, method, system, user)).reply == "ready"
        assert (await ask(client, method, system, user)).reply == "ready"

    asyncio.run(exercise())
    assert len(seen) == 2  # One invalid answer, one correction, then a cache hit.
    assert client.get_usage().requests == 3 and client.get_usage().cached_requests == 1
    for body in seen:
        messages = body["messages"]
        system_text = next(m["content"] for m in messages if m["role"] == "system")
        assert system_text.startswith(system)
        if mode == "json_schema":
            assert body["response_format"]["json_schema"]["schema"] == schema
            assert system_text == system
        else:
            assert body["response_format"] == {"type": "json_object"}
            assert (minified if compact else pretty) in system_text
            assert (pretty if compact else minified) not in system_text
        original_user = next(m["content"] for m in messages if m["role"] == "user")
        if method.endswith("image"):
            assert original_user == [{"type": "text", "text": user},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,AA=="}}]
        else:
            assert original_user == user


@pytest.mark.parametrize("base", ["http://localhost:8081/v1", "http://localhost.:8081/v1", "http://[::1]:8081/v1"])
def test_localhost_and_ipv6_use_the_compact_schema(tmp_path, monkeypatch, base):
    seen = responses(monkeypatch)
    client = LiteLLMClient(config(tmp_path, "json", base))
    assert client.generate_structured(Answer, "Answer", "Hello").reply == "ready"
    assert json.dumps(Answer.model_json_schema(), separators=(",", ":"), ensure_ascii=False) in seen[0]["messages"][0]["content"]


@pytest.mark.parametrize("mode,base,refresh", [
    ("json", "http://127.0.0.1:8081/v1", True),
    ("json", "http://model.example.invalid/v1", False),
    ("json_schema", "http://127.0.0.1:8081/v1", False),
])
def test_only_changed_prompts_invalidate_legacy_cache(tmp_path, monkeypatch, mode, base, refresh):
    seen = responses(monkeypatch)
    client = LiteLLMClient(config(tmp_path, mode, base))
    system, user = "Answer", "Hello"
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    legacy = {"structured_parser": "final-think-v2", "structured_output": mode,
        "model": client.model, "api_base": base, "temperature": client.temperature, "max_tokens": 160,
        "seed": None, "schema": Answer.model_json_schema(), "messages": messages}
    digest = hashlib.sha256(json.dumps(legacy, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    path = tmp_path / digest[:2] / f"{digest}.json"
    path.parent.mkdir()
    original = json.dumps({"result": {"updates": [], "reply": "previous schema prompt"}})
    path.write_text(original)
    assert client.generate_structured(Answer, system, user).reply == ("ready" if refresh else "previous schema prompt")
    assert len(seen) == int(refresh)
    assert client.get_usage().cached_requests == int(not refresh)
    assert path.read_text() == original


def test_small_local_schema_keeps_original_prompt_and_cache(tmp_path, monkeypatch):
    seen = responses(monkeypatch)
    client = LiteLLMClient(config(tmp_path, "json", "http://127.0.0.1:8081/v1"))
    assert client.generate_structured(SmallAnswer, "Answer", "First").reply == "ready"
    schema = SmallAnswer.model_json_schema()
    assert json.dumps(schema, indent=2, ensure_ascii=False) in seen[0]["messages"][0]["content"]
    messages = [{"role": "system", "content": "Answer"}, {"role": "user", "content": "Second"}]
    legacy = {"structured_parser": "final-think-v2", "structured_output": "json",
        "model": client.model, "api_base": client.api_base, "temperature": client.temperature,
        "max_tokens": 160, "seed": None, "schema": schema, "messages": messages}
    digest = hashlib.sha256(json.dumps(legacy, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    path = tmp_path / digest[:2] / f"{digest}.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps({"result": {"reply": "previous small prompt"}}))
    assert client.generate_structured(SmallAnswer, "Answer", "Second").reply == "previous small prompt"
    assert len(seen) == 1 and client.get_usage().cached_requests == 1
