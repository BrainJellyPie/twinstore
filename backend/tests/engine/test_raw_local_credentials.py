"""Direct local model configs must honor their explicitly configured local credential."""

import asyncio
import json

import httpx
import pytest
from pydantic import BaseModel, SecretStr

from store_emulator.application import providers
from store_emulator.domain.config import VLMGlanceConfig
from store_emulator.engine.llm_client import LiteLLMClient


class Answer(BaseModel):
    text: str


@pytest.mark.parametrize("mode", ["sync", "sync_image", "async", "async_image", "text"])
@pytest.mark.parametrize("endpoint,local_key,cloud_key,explicit,expected", [
    ("http://127.0.0.1:8081/v1", "local", "cloud", None, "local"),
    ("http://127.2.3.4:8081/v1", "local", "cloud", None, "local"),
    ("http://localhost:8081/v1", "local", "cloud", None, "local"),
    ("http://LOCALHOST.:8081/v1", "local", "cloud", None, "local"),
    ("http://[::1]:8081/v1", "local", "cloud", None, "local"),
    ("http://[0:0:0:0:0:0:0:1]:8081/v1", "local", "cloud", None, "local"),
    ("http://127.0.0.1:8081/v1", "  local  ", "cloud", None, "local"),
    ("http://127.0.0.1:8081/v1", "local", "cloud", "saved", "saved"),
    ("http://127.0.0.1:8081/v1", None, "cloud", None, "cloud"),
    ("http://127.0.0.1:8081/v1", "", "cloud", None, "cloud"),
    ("http://127.0.0.1:8081/v1", None, None, None, "not-needed"),
    ("https://gateway.invalid/v1", "local", "cloud", None, "cloud"),
    ("http://localhost.example/v1", "local", "cloud", None, "cloud"),
    ("http://192.168.1.2:8001/v1", "local", "cloud", None, "cloud"),
    ("https://api.openai.com/v1", "local", "cloud", None, "cloud"),
    ("https://gateway.invalid/v1", "local", None, None, "local"),
])
def test_raw_model_credentials_at_the_http_boundary(monkeypatch, mode, endpoint, local_key, cloud_key, explicit, expected):
    for name, value in [("PARASTORE_LOCAL_API_KEY", local_key), ("OPENAI_API_KEY", cloud_key)]:
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, "offline-" + value if value and value == value.strip() else value.replace("local", "offline-local"))
    monkeypatch.setattr(providers, "_on_local_server", lambda config: config)
    monkeypatch.setattr(providers, "_local_cache_namespace", lambda base: "")
    expected = expected if expected == "not-needed" else "offline-" + expected
    requests = []

    def respond(request):
        requests.append(request)
        if request.headers.get("authorization") != f"Bearer {expected}":
            return httpx.Response(401, request=request, json={"error": {"message": "Wrong local credential"}})
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": "local-vlm", "choices": [{"index": 0, "finish_reason": "stop", "message": {
                "role": "assistant", "content": json.dumps({"text": "ok"})}}]})

    def send(self, request, *args, **kwargs):
        return respond(request)

    async def asend(self, request, *args, **kwargs):
        return respond(request)

    monkeypatch.setattr(httpx.Client, "send", send)
    monkeypatch.setattr(httpx.AsyncClient, "send", asend)
    base = VLMGlanceConfig().llm.model_copy(update={"api_base": endpoint,
        "api_key": SecretStr("offline-" + explicit) if explicit else None})
    config = providers.resolve_model(base.model, base=base, settings={})
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
    assert "api_key" not in config.model_dump()
    assert expected not in config.model_dump_json()
