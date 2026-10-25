"""Trailing endpoint slashes must not produce a different native Ollama route."""

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


@pytest.mark.parametrize("mode", ["sync", "sync_image", "async", "async_image", "text"])
@pytest.mark.parametrize("named", [False, True])
@pytest.mark.parametrize("endpoint,path", [
    ("http://127.0.0.1:11434/", "/api/chat"),
    ("http://localhost:11434///", "/api/chat"),
    ("http://[::1]:11434/", "/api/chat"),
    ("https://proxy.invalid/ollama/", "/ollama/api/chat"),
    ("http://127.0.0.1:11434/api/chat/", "/api/chat"),
    ("http://127.0.0.1:11434", "/api/chat"),
])
def test_native_request_reaches_the_same_route_with_trailing_slashes(monkeypatch, tmp_path, mode, named, endpoint, path):
    monkeypatch.setattr(providers, "_local_slots", lambda base: None)
    monkeypatch.setattr(providers, "_local_cache_namespace", lambda base: "")
    requests = []

    def respond(request):
        if request.url.path.endswith("/api/show"):
            return httpx.Response(200, request=request, json={"model_info": {}, "capabilities": ["completion", "vision"]})
        requests.append((request.url.path, json.loads(request.content)))
        if request.url.path != path:
            return httpx.Response(404, request=request, json={"error": "No such native model route"})
        return httpx.Response(200, request=request, json={"model": "slash-model", "created_at": "2026-10-25T00:00:00Z",
            "message": {"role": "assistant", "content": '{"text":"ok"}'}, "done": True, "done_reason": "stop",
            "prompt_eval_count": 10, "eval_count": 5})

    def send(self, request, *args, **kwargs): return respond(request)
    async def asend(self, request, *args, **kwargs): return respond(request)
    monkeypatch.setattr(httpx.Client, "send", send)
    monkeypatch.setattr(httpx.AsyncClient, "send", asend)
    base = LLMConfig(model="ollama_chat/slash-model", api_base=endpoint, cache_dir=str(tmp_path), seed=0)
    config = providers.resolve_model("ollama:slash-model", base=base, settings={ProviderKind.OLLAMA:
        providers.ProviderSettings(kind=ProviderKind.OLLAMA, api_base=endpoint)}) if named else base
    client = LiteLLMClient(config)

    def ask():
        if mode == "sync":
            return client.generate_structured(Answer, "Return JSON.", "Reply ok.")
        if mode == "sync_image":
            return client.generate_structured_with_image(Answer, "Return JSON.", "Reply ok.", "data:image/png;base64,AA==")
        if mode == "async":
            return asyncio.run(client.generate_structured_async(Answer, "Return JSON.", "Reply ok."))
        if mode == "async_image":
            return asyncio.run(client.generate_structured_with_image_async(Answer, "Return JSON.", "Reply ok.", "data:image/png;base64,AA=="))
        return Answer.model_validate_json(asyncio.run(client.generate_text_async("Return JSON.", "Reply ok.")))

    assert ask().text == "ok"
    assert config.api_base == endpoint  # Resolution must not rewrite saved settings.
    assert len(requests) == 1 and requests[0][0] == path
    if mode != "text":
        assert ask().text == "ok" and len(requests) == 1 and client.get_usage().cached_requests == 1


@pytest.mark.parametrize("model,endpoint", [
    ("openai/local", "https://gateway.invalid/v1/"),
    ("ollama_chat/local", "https://proxy.invalid/ollama/?token=value/"),
    ("ollama_chat/local", "https://proxy.invalid/ollama/#fragment/"),
])
def test_other_provider_urls_and_query_or_fragment_values_are_not_rewritten(model, endpoint):
    client = LiteLLMClient(LLMConfig(model=model, api_base=endpoint))
    assert client._call_kwargs(None)["api_base"] == endpoint
