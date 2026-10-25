"""Ollama must reject oversized inputs instead of quietly discarding requirements."""

import asyncio
import hashlib
import json
from collections import Counter

import httpx
import pytest
from instructor.core.exceptions import InstructorRetryException
from litellm.exceptions import APIConnectionError
from pydantic import BaseModel

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.starter_fill import StarterRack
from store_emulator.engine.llm_client import LiteLLMClient, is_context_overflow
from store_emulator.engine.starter_selection import select_starter_products
from tests.engine.test_starter_selection import empty_store


TOO_LONG = ("the prompt is longer than the context length currently available to the model; shorten the prompt, "
            "adjust the context length in settings, or use a model with a longer context length")


class Reply(BaseModel):
    text: str


@pytest.fixture
def native_http(monkeypatch):
    def install(respond):
        def response(request):
            if request.url.path.endswith("/api/show"):
                return httpx.Response(200, request=request, json={"model_info": {}, "capabilities": ["completion", "vision"]})
            status, answer = respond(json.loads(request.content))
            body = {"error": answer} if status != 200 else {"model": "local-context", "done": True, "done_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(answer)}, "prompt_eval_count": 10, "eval_count": 5}
            return httpx.Response(status, request=request, json=body)
        def send(self, request, *args, **kwargs): return response(request)
        async def asend(self, request, *args, **kwargs): return response(request)
        monkeypatch.setattr(httpx.Client, "send", send)
        monkeypatch.setattr(httpx.AsyncClient, "send", asend)
    return install


@pytest.mark.parametrize("mode", ["sync", "sync_image", "async", "async_image", "text"])
@pytest.mark.parametrize("structured", ["json", "json_schema"])
def test_native_input_preservation_is_top_level_in_every_call(native_http, mode, structured):
    calls = []
    def respond(body):
        calls.append(body)
        return 200, {"text": "ready"}
    native_http(respond)
    client = LiteLLMClient(LLMConfig(model="ollama_chat/local-context", api_base="http://127.0.0.1:11434", structured_output=structured))
    args = (Reply, "Keep all requirements.", "동네 주민; exact product choices.")
    if mode == "sync": result = client.generate_structured(*args)
    elif mode == "sync_image": result = client.generate_structured_with_image(*args, "data:image/png;base64,AA==")
    elif mode == "async": result = asyncio.run(client.generate_structured_async(*args))
    elif mode == "async_image": result = asyncio.run(client.generate_structured_with_image_async(*args, "data:image/png;base64,AA=="))
    else: result = Reply.model_validate_json(asyncio.run(client.generate_text_async(*args[1:])))
    assert result.text == "ready" and len(calls) == 1
    assert calls[0].get("truncate") is False
    assert "truncate" not in calls[0].get("options", {})
    assert any("동네 주민" in message["content"] for message in calls[0]["messages"])


@pytest.mark.parametrize("status", [400, 401, 403, 429, 500])
@pytest.mark.parametrize("message", [TOO_LONG, "The context length parameter is not supported by this endpoint"])
def test_native_context_error_requires_the_real_bad_request_status(native_http, status, message):
    calls = []
    def respond(body):
        calls.append(body)
        return status, message
    native_http(respond)
    client = LiteLLMClient(LLMConfig(model="ollama_chat/local-context", api_base="http://127.0.0.1:11434", structured_output="json_schema"))
    with pytest.raises(InstructorRetryException) as caught:
        asyncio.run(client.generate_structured_async(Reply, "Reply", "Hello", max_retries=2))
    error = caught.value.failed_attempts[-1].exception
    assert is_context_overflow(error) is (status == 400 and message == TOO_LONG)
    assert len(calls) == 2


@pytest.mark.parametrize("count", [1, 9, 17])
def test_native_catalog_overflow_splits_without_silently_ignoring_requirements(native_http, tmp_path, count):
    calls = []
    ids = [f"section_{i}" for i in range(count)]
    def respond(body):
        context = json.loads(body["messages"][-1]["content"])
        calls.append((body, context))
        if "expected_rack_ids" in context:
            if body.get("truncate") is False:
                return 400, TOO_LONG
            # A syntactically valid answer after silent loss of the coffee-only
            # requirement cannot be distinguished by schema validation alone.
            return 200, {"groups": [{"category": "dairy", "rack_ids": ids}]}
        if isinstance(context.get("categories"), dict):
            return 200, {"groups": [{"category": key, "skus": [products[0]["sku"]]} for key, products in context["categories"].items()]}
        return 200, {"choices": ["home_coffee_tea"] * len(context["racks"])}
    native_http(respond)
    client = LiteLLMClient(LLMConfig(model="ollama_chat/local-context", api_base="http://127.0.0.1:11434",
        structured_output="json_schema", cache_dir=str(tmp_path)))
    store = empty_store()
    before = store.model_dump_json()
    racks = [StarterRack(id=rid, name=f"Coffee shelf {i}", type="shelf", available_slots=2) for i, rid in enumerate(ids)]
    result = asyncio.run(select_starter_products(client, store, racks, "Coffee products only. 동네 주민",
        allowed_categories={"home_coffee_tea", "dairy"}))
    assert Counter(row.rack_id for row in result) == Counter(ids)
    assert all(row.category == "home_coffee_tea" for row in result)
    assert sum("expected_rack_ids" in context for _, context in calls) == 2
    assert all(context["requirements"] == "Coffee products only. 동네 주민" for _, context in calls)
    assert all(body.get("truncate") is False for body, _ in calls)
    assert store.model_dump_json() == before


@pytest.mark.parametrize("child_status", [400, 403, 429, 500])
def test_native_overflow_that_cannot_fit_one_rack_stops_without_partial_results(native_http, child_status):
    calls = []
    def respond(body):
        calls.append(body)
        return 400 if "expected_rack_ids" in json.loads(body["messages"][-1]["content"]) else child_status, TOO_LONG
    native_http(respond)
    client = LiteLLMClient(LLMConfig(model="ollama_chat/local-context", api_base="http://127.0.0.1:11434", structured_output="json_schema"))
    store = empty_store()
    before = store.model_dump_json()
    with pytest.raises(ValueError if child_status == 400 else InstructorRetryException, match="context"):
        asyncio.run(select_starter_products(client, store, [StarterRack(id="a", name="Coffee", type="shelf", available_slots=2)], ""))
    assert len(calls) == 4 and store.model_dump_json() == before


def test_a_native_connection_error_without_an_original_http_400_does_not_trigger_recovery():
    error = APIConnectionError(message=TOO_LONG, model="local-context", llm_provider="ollama_chat")
    assert not is_context_overflow(error)


def test_old_ollama_cache_cannot_hide_input_truncation(tmp_path):
    client = LiteLLMClient(LLMConfig(model="ollama_chat/local-context", api_base="http://127.0.0.1:11434", cache_dir=str(tmp_path)))
    messages = [{"role": "user", "content": "Hello"}]
    old_key = hashlib.sha256(json.dumps({"ollama_finish_reason": "native-v1", "structured_parser": "final-think-v2",
        "model": client.model, "api_base": client.api_base, "temperature": client.temperature, "max_tokens": client.max_tokens,
        "seed": client._effective_seed(None), "schema": Reply.model_json_schema(), "messages": messages},
        sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    old_path = tmp_path / old_key[:2] / f"{old_key}.json"
    client._cache_put(old_path, Reply(text="ignored requirements"))
    assert client._cache_get(client._cache_path(Reply, messages, None), Reply) is None
    assert old_path.exists()


@pytest.mark.parametrize("model,endpoint", [("openai/local", "http://127.0.0.1:8081/v1"),
    ("openai/local", "http://127.0.0.1:11434/v1"), ("anthropic/claude-test", None)])
def test_native_control_is_not_sent_to_other_protocols(model, endpoint):
    client = LiteLLMClient(LLMConfig(model=model, api_base=endpoint))
    assert "truncate" not in client._call_kwargs(None).get("extra_body", {})
