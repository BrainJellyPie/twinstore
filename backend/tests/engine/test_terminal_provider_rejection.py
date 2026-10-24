"""Old provider rejections cannot invalidate keys or sampling options after a different failure."""

import asyncio
import json

import httpx
import pytest

from store_emulator.domain.config import LLMConfig
from store_emulator.engine import llm_client
from tests.engine.test_llm_retry_usage import exercise, response


@pytest.mark.parametrize("mode", ["sync", "async", "sync_image", "async_image"])
@pytest.mark.parametrize("first", ["auth", "parameter"])
@pytest.mark.parametrize("last", ["validation", "truncation", "timeout"])
def test_terminal_response_failure_does_not_learn_stale_provider_rejection(monkeypatch, tmp_path, mode, first, last):
    monkeypatch.setattr(llm_client, "_REJECTED", {})
    monkeypatch.setattr(llm_client, "_THINKING_OFF", {})
    calls, reroutes = [], []

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        if body["model"] != "local-usage":
            return response(request, '{"text":"wrong fallback"}')
        if len(calls) == 1:
            return httpx.Response(401 if first == "auth" else 400, request=request, json={"error": {
                "message": "invalid api key" if first == "auth" else "Unsupported parameter: temperature is not supported",
                "type": "authentication_error" if first == "auth" else "invalid_request_error"}})
        if last == "timeout":
            raise httpx.ReadTimeout("offline timeout", request=request)
        return response(request, '{"text":17}', finish="length" if last == "truncation" else "stop")

    def reroute(model, error):
        reroutes.append(model)
        return LLMConfig(model="openai/local-backup", api_base="http://127.0.0.1:8081/v1", cache_dir=str(tmp_path))

    asyncio.run(exercise(monkeypatch, mode, respond, str(tmp_path), succeed=False, attempts=2, reroute=reroute))
    assert not reroutes, "A stale authentication error incorrectly invoked the key-rejection/provider-switch callback"
    assert not llm_client._REJECTED and not llm_client._THINKING_OFF
    assert len(calls) == 2
    assert not list(tmp_path.rglob("*.json"))
