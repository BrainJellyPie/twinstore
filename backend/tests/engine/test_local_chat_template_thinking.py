"""Self-hosted template reasoning must not consume short structured-answer budgets."""

import asyncio
import json

import httpx
import pytest
from pydantic import BaseModel

from store_emulator.application import providers
from store_emulator.domain.config import LLMConfig
from store_emulator.domain.providers import ProviderKind
from store_emulator.engine.llm_client import LiteLLMClient


class Answer(BaseModel):
    text: str


@pytest.mark.parametrize("kind", [ProviderKind.LLAMACPP, ProviderKind.VLLM])
@pytest.mark.parametrize("model", ["Qwen/Qwen3-8B", "Qwen/Qwen3.5-9B", "served-model"])
@pytest.mark.parametrize("mode", ["sync", "sync_image", "async", "async_image", "text"])
def test_template_switch_reaches_every_request_without_consuming_the_answer_budget(monkeypatch, kind, model, mode):
    monkeypatch.setattr(providers, "_local_slots", lambda base: None)
    monkeypatch.setattr(providers, "_local_cache_namespace", lambda base: "")
    settings = {kind: providers.ProviderSettings(kind=kind, api_base="http://127.0.0.1:8081/v1")}
    requests = []

    def respond(request):
        body = json.loads(request.content)
        requests.append(body)
        disabled = body.get("chat_template_kwargs", {}).get("enable_thinking") is False
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop" if disabled else "length",
                "message": {"role": "assistant", "content": '{"text":"ready"}' if disabled else "",
                            "reasoning_content": "" if disabled else "Reasoning before the answer..."}}]})

    def send(self, request, *args, **kwargs):
        return respond(request)

    async def asend(self, request, *args, **kwargs):
        return respond(request)

    monkeypatch.setattr(httpx.Client, "send", send)
    monkeypatch.setattr(httpx.AsyncClient, "send", asend)
    config = providers.resolve_model(f"{kind.value}:{model}", base=LLMConfig(max_tokens=160), settings=settings)
    client = LiteLLMClient(config)
    if mode == "sync":
        result = client.generate_structured(Answer, "Answer directly.", "Reply ready.")
    elif mode == "sync_image":
        result = client.generate_structured_with_image(Answer, "Answer directly.", "Reply ready.", "offline-image")
    elif mode == "async":
        result = asyncio.run(client.generate_structured_async(Answer, "Answer directly.", "Reply ready."))
    elif mode == "async_image":
        result = asyncio.run(client.generate_structured_with_image_async(Answer, "Answer directly.", "Reply ready.", "offline-image"))
    else:
        result = Answer.model_validate_json(asyncio.run(client.generate_text_async("Answer directly.", "Reply ready.")))
    assert result.text == "ready" and len(requests) == 1
    assert requests[0]["chat_template_kwargs"] == {"enable_thinking": False}
    assert requests[0]["max_tokens"] == 160
    assert "enable_thinking" not in requests[0] and "reasoning_effort" not in requests[0]


@pytest.mark.parametrize("ref", ["openai:gpt-test", "qwen:qwen-test", "custom:Qwen/Qwen3-8B", "ollama:qwen3:8b"])
def test_local_template_policy_is_not_inherited_by_other_named_providers(monkeypatch, ref):
    monkeypatch.setenv("OPENAI_API_KEY", "offline")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "offline")
    monkeypatch.setattr(providers, "_local_slots", lambda base: None)
    monkeypatch.setattr(providers, "_local_cache_namespace", lambda base: "")
    local = providers.resolve_model("vllm:Qwen/Qwen3-8B", settings={})
    settings = {ProviderKind.CUSTOM: providers.ProviderSettings(kind=ProviderKind.CUSTOM, api_base="https://gateway.invalid/v1")}
    config = providers.resolve_model(ref, base=local, settings=settings)
    kwargs = LiteLLMClient(config)._call_kwargs(None)
    assert "chat_template_kwargs" not in kwargs.get("extra_body", {})
    assert "chat_template_thinking" not in config.model_dump()


def test_template_policy_separates_cached_answers(monkeypatch, tmp_path):
    monkeypatch.setattr(providers, "_local_slots", lambda base: None)
    monkeypatch.setattr(providers, "_local_cache_namespace", lambda base: "")
    resolved = providers.resolve_model("vllm:Qwen/Qwen3-8B", base=LLMConfig(cache_dir=str(tmp_path)), settings={})
    raw = LLMConfig.model_validate(resolved.model_dump())
    messages = [{"role": "user", "content": "Reply ready."}]
    a, b = LiteLLMClient(resolved), LiteLLMClient(raw)
    assert a._cache_path(Answer, messages, None) != b._cache_path(Answer, messages, None)
    path = b._cache_path(Answer, messages, None)
    b._cache_put(path, Answer(text="old policy"))
    assert a._cache_get(a._cache_path(Answer, messages, None), Answer) is None
    assert b._cache_get(path, Answer).text == "old policy"
