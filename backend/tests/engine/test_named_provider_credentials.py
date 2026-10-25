"""A named self-hosted provider must not inherit another provider's environment credential."""

import asyncio
import json

import httpx
import pytest
from pydantic import BaseModel, SecretStr

from store_emulator.application import providers
from store_emulator.domain.providers import ProviderKind
from store_emulator.engine.llm_client import LiteLLMClient


class Answer(BaseModel):
    text: str


@pytest.mark.parametrize("kind", [ProviderKind.LLAMACPP, ProviderKind.VLLM, ProviderKind.CUSTOM])
@pytest.mark.parametrize("cloud_key", [False, True])
@pytest.mark.parametrize("local_key", [False, True])
@pytest.mark.parametrize("mode", ["sync", "sync_image", "async", "async_image", "text"])
def test_only_the_selected_providers_credential_or_placeholder_reaches_its_server(monkeypatch, kind, cloud_key, local_key, mode):
    for name, enabled, value in [("OPENAI_API_KEY", cloud_key, "offline-cloud-key"),
                                 ("PARASTORE_LOCAL_API_KEY", local_key, "offline-local-key")]:
        if enabled:
            monkeypatch.setenv(name, value)
        else:
            monkeypatch.delenv(name, raising=False)
    monkeypatch.delenv("CUSTOM_LLM_API_KEY", raising=False)
    monkeypatch.setattr(providers, "_local_slots", lambda base: None)
    monkeypatch.setattr(providers, "_local_cache_namespace", lambda base: "")
    expected = "offline-local-key" if local_key and kind != ProviderKind.CUSTOM else "not-needed"
    endpoint = "http://named-provider.invalid/v1"
    settings = {kind: providers.ProviderSettings(kind=kind, enabled=True, api_base=endpoint)}
    requests = []

    def respond(request):
        requests.append(request)
        assert request.url.host == "named-provider.invalid"
        if request.headers.get("authorization") != f"Bearer {expected}":
            return httpx.Response(401, request=request, json={"error": {"message": "Wrong provider credential"}})
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": "local-model", "choices": [{"index": 0, "finish_reason": "stop", "message": {
                "role": "assistant", "content": json.dumps({"text": "ok"})}}]})

    def send(self, request, *args, **kwargs):
        return respond(request)

    async def asend(self, request, *args, **kwargs):
        return respond(request)

    monkeypatch.setattr(httpx.Client, "send", send)
    monkeypatch.setattr(httpx.AsyncClient, "send", asend)
    model = "local" if kind == ProviderKind.LLAMACPP else "served"
    config = providers.resolve_model(f"{kind.value}:{model}", settings=settings)
    client = LiteLLMClient(config)
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
    assert result.text == "ok" and len(requests) == 1
    assert requests[0].headers["authorization"] == f"Bearer {expected}"
    assert "api_key" not in config.model_dump() and expected not in config.model_dump_json()
    status = providers.provider_status(kind, settings)
    assert status.has_key is (local_key and kind != ProviderKind.CUSTOM)
    assert settings[kind].api_key is None


@pytest.mark.parametrize("source", ["environment", "saved", "both"])
def test_custom_providers_own_credential_retains_precedence(monkeypatch, source):
    monkeypatch.setenv("OPENAI_API_KEY", "offline-cloud-key")
    monkeypatch.setenv("PARASTORE_LOCAL_API_KEY", "offline-unrelated-local-key")
    if source != "saved":
        monkeypatch.setenv("CUSTOM_LLM_API_KEY", "offline-custom-environment-key")
    else:
        monkeypatch.delenv("CUSTOM_LLM_API_KEY", raising=False)
    monkeypatch.setattr(providers, "_local_cache_namespace", lambda base: "")
    saved = source != "environment"
    settings = {ProviderKind.CUSTOM: providers.ProviderSettings(kind=ProviderKind.CUSTOM,
        api_base="http://named-provider.invalid/v1", api_key=SecretStr("offline-custom-saved-key") if saved else None)}
    config = providers.resolve_model("custom:served", settings=settings)
    expected = "offline-custom-saved-key" if saved else "offline-custom-environment-key"
    assert LiteLLMClient(config)._call_kwargs(None)["api_key"] == expected
    status = providers.provider_status(ProviderKind.CUSTOM, settings)
    assert status.has_key and status.key_source == ("settings" if saved else "env")
    assert expected not in config.model_dump_json() and expected not in status.model_dump_json()
