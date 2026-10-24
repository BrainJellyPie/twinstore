"""Known self-hosted providers must resolve their own key before OpenAI environment fallback."""

import asyncio
import json

import httpx
import pytest
from pydantic import BaseModel, SecretStr

from store_emulator.application import providers
from store_emulator.domain.providers import ProviderKind
from store_emulator.engine import llm_client


class Answer(BaseModel):
    text: str


@pytest.mark.parametrize("kind", [ProviderKind.LLAMACPP, ProviderKind.VLLM])
@pytest.mark.parametrize("mode", ["sync", "sync_image", "async", "async_image", "text"])
@pytest.mark.parametrize("saved", [False, True])
@pytest.mark.parametrize("cloud_key", [False, True])
def test_local_authentication_uses_local_or_saved_key_even_with_openai_connected(
    monkeypatch, kind, mode, saved, cloud_key,
):
    monkeypatch.setenv("PARASTORE_LOCAL_API_KEY", "offline-local-key")
    if cloud_key:
        monkeypatch.setenv("OPENAI_API_KEY", "offline-cloud-key")
    else:
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(providers, "_local_slots", lambda base: None)
    monkeypatch.setattr(providers, "_local_cache_namespace", lambda base: "")
    expected = "offline-saved-key" if saved else "offline-local-key"
    settings = {kind: providers.ProviderSettings(kind=kind, api_base="http://local-key.invalid/v1",
                api_key=SecretStr(expected) if saved else None)}
    requests = []

    def respond(request):
        requests.append(request)
        assert request.url.host == "local-key.invalid"
        if request.headers.get("authorization") != f"Bearer {expected}":
            return httpx.Response(401, request=request, json={"error": {
                "message": "Invalid API key for local server", "type": "authentication_error", "code": "invalid_api_key"}})
        return httpx.Response(200, request=request, json={
            "id": "offline-local-auth", "object": "chat.completion", "created": 0, "model": "local-model",
            "choices": [{"index": 0, "finish_reason": "stop", "message": {
                "role": "assistant", "content": json.dumps({"text": "ok"})}}]})

    def send(self, request, *args, **kwargs):
        return respond(request)

    async def asend(self, request, *args, **kwargs):
        return respond(request)

    monkeypatch.setattr(httpx.Client, "send", send)
    monkeypatch.setattr(httpx.AsyncClient, "send", asend)
    model = "local" if kind == ProviderKind.LLAMACPP else "served"
    config = providers.resolve_model(f"{kind.value}:{model}", settings=settings)
    client = llm_client.LiteLLMClient(config)
    if mode == "sync":
        result = client.generate_structured(Answer, "system", "request")
    elif mode == "sync_image":
        result = client.generate_structured_with_image(Answer, "system", "request", "offline-image")
    elif mode == "async":
        result = asyncio.run(client.generate_structured_async(Answer, "system", "request"))
    elif mode == "async_image":
        result = asyncio.run(client.generate_structured_with_image_async(Answer, "system", "request", "offline-image"))
    else:
        result = Answer.model_validate_json(asyncio.run(client.generate_text_async("system", "request")))
    assert result.text == "ok"
    assert len(requests) == 1
    assert requests[0].headers["authorization"] == f"Bearer {expected}"
    assert "api_key" not in config.model_dump() and expected not in config.model_dump_json()


@pytest.mark.parametrize("kind,env,model", [
    (ProviderKind.OPENAI, "OPENAI_API_KEY", "gpt-test"),
    (ProviderKind.ANTHROPIC, "ANTHROPIC_API_KEY", "claude-test"),
    (ProviderKind.GEMINI, "GEMINI_API_KEY", "gemini-test"),
])
def test_local_key_does_not_replace_cloud_provider_credentials(monkeypatch, kind, env, model):
    monkeypatch.setenv("PARASTORE_LOCAL_API_KEY", "offline-local-key")
    monkeypatch.setenv(env, "offline-provider-key")
    monkeypatch.setattr(providers, "_local_cache_namespace", lambda base: "")
    config = providers.resolve_model(f"{kind.value}:{model}", settings={})
    assert config.api_key.get_secret_value() == "offline-provider-key"
    assert llm_client.LiteLLMClient(config)._call_kwargs(None)["api_key"] == "offline-provider-key"
