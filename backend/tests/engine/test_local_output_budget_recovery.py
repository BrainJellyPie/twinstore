"""Older vLLM deployments reject output ceilings larger than their remaining context."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI, OpenAI
from pydantic import BaseModel

from store_emulator.domain.config import LLMConfig
from store_emulator.engine import llm_client


class Answer(BaseModel):
    text: str


def rejection(requested, context, inputs):
    # vLLM v0.11.0, entrypoints/openai/serving_engine.py::_validate_input.
    return (f"'max_tokens' or 'max_completion_tokens' is too large: {requested}. "
            f"This model's maximum context length is {context} tokens and your request has "
            f"{inputs} input tokens ({requested} > {context} - {inputs}).")


async def exercise(monkeypatch, mode, respond, *, cache_dir=None, maximum=65535, override=None, reroute=None, retries=1):
    original_sync = llm_client.litellm.completion
    original_async = llm_client.litellm.acompletion
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as ah:
        with httpx.Client(transport=httpx.MockTransport(respond)) as sh:
            sync = OpenAI(api_key="offline", base_url="http://local.invalid/v1", http_client=sh, max_retries=0)
            async_client = AsyncOpenAI(api_key="offline", base_url="http://local.invalid/v1", http_client=ah, max_retries=0)

            def completion(**kwargs):
                return original_sync(**{**kwargs, "client": sync, "api_key": "offline", "num_retries": 0})

            async def acompletion(**kwargs):
                return await original_async(**{**kwargs, "client": async_client, "api_key": "offline", "num_retries": 0})

            monkeypatch.setattr(llm_client.litellm, "completion", completion)
            monkeypatch.setattr(llm_client.litellm, "acompletion", acompletion)
            client = llm_client.LiteLLMClient(LLMConfig(model="openai/local-output-budget", api_base="http://local.invalid/v1",
                max_tokens=maximum, structured_output="json_schema", cache_dir=cache_dir), reroute=reroute)
            async def ask(prompt):
                if mode == "raw":
                    return await client.generate_text_async("Reply briefly", prompt)
                kwargs = {"max_retries": retries, **({"max_tokens": override} if override is not None else {})}
                if mode == "sync":
                    return client.generate_structured(Answer, "Reply briefly", prompt, **kwargs)
                if mode == "async":
                    return await client.generate_structured_async(Answer, "Reply briefly", prompt, **kwargs)
                if mode == "sync_image":
                    return client.generate_structured_with_image(Answer, "Reply briefly", prompt, "data:image/png;base64,AA==", **kwargs)
                return await client.generate_structured_with_image_async(Answer, "Reply briefly", prompt, "data:image/png;base64,AA==", **kwargs)

            first = await ask("first")
            second = await ask("second")
            if mode != "raw" and cache_dir:
                assert (await ask("first")).text == "ready"
                assert client.get_usage().cached_requests == 1
            if reroute is None:
                assert client.max_tokens == maximum
            return first, second


@pytest.mark.parametrize("mode", ["sync", "async", "sync_image", "async_image", "raw"])
@pytest.mark.parametrize("context,inputs", [(8192, 1024), (32768, 3000), (131072, 131000)])
def test_server_reported_remaining_room_is_request_local_and_success_is_cacheable(monkeypatch, tmp_path, mode, context, inputs):
    budgets = []
    for_model = []

    def respond(request):
        body = json.loads(request.content)
        budget = body.get("max_tokens", body.get("max_completion_tokens"))
        budgets.append(budget)
        text = str(body["messages"][-1]["content"])
        remaining = context - inputs - (1 if "second" in text else 0)
        if budget > remaining:
            return httpx.Response(400, request=request, json={"error": {"type": "BadRequestError", "code": 400,
                "message": rejection(budget, context, context - remaining)}})
        for_model.append(body["model"])
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": '{"text":"ready"}'}}]})

    first, second = asyncio.run(exercise(monkeypatch, mode, respond, cache_dir=str(tmp_path)))
    assert (first if mode == "raw" else first.text) == ('{"text":"ready"}' if mode == "raw" else "ready")
    assert second == first if mode == "raw" else second.text == first.text
    assert budgets == [65535, context - inputs, 65535, context - inputs - 1]
    assert len(for_model) == 2


@pytest.mark.parametrize("mode", ["async", "async_image"])
def test_explicit_per_call_budget_can_be_reduced_without_changing_configuration(monkeypatch, mode):
    budgets = []

    def respond(request):
        body = json.loads(request.content)
        budget = body["max_tokens"]
        budgets.append(budget)
        if budget > 384:
            return httpx.Response(400, request=request, json={"error": {"message": rejection(budget, 512, 128), "type": "BadRequestError"}})
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": '{"text":"ready"}'}}]})

    asyncio.run(exercise(monkeypatch, mode, respond, override=1024))
    assert budgets == [1024, 384, 1024, 384]


@pytest.mark.parametrize("mode", ["sync", "async", "raw"])
@pytest.mark.parametrize("kind", ["input_full", "input_too_long", "different_request", "larger_budget", "unrelated", "forbidden", "rate_limit"])
def test_only_a_matching_output_ceiling_rejection_is_adapted(monkeypatch, mode, kind):
    calls = []
    messages = {
        "input_full": rejection(65535, 8192, 8192),
        "input_too_long": rejection(65535, 8192, 9000),
        "different_request": rejection(10000, 8192, 1024),
        "larger_budget": rejection(65535, 131072, 1024),
        "unrelated": "This model's maximum context length is 8192 tokens. However, your request has 9000 input tokens.",
        "forbidden": rejection(65535, 8192, 1024),
        "rate_limit": rejection(65535, 8192, 1024),
    }

    def respond(request):
        calls.append(json.loads(request.content))
        return httpx.Response({"forbidden": 403, "rate_limit": 429}.get(kind, 400), request=request,
            json={"error": {"message": messages[kind], "type": "BadRequestError"}})

    with pytest.raises(Exception):
        asyncio.run(exercise(monkeypatch, mode, respond))
    assert len(calls) == 1


@pytest.mark.parametrize("mode", ["sync", "async", "raw"])
def test_a_second_output_ceiling_rejection_stops_after_one_adjustment(monkeypatch, mode):
    budgets = []

    def respond(request):
        body = json.loads(request.content)
        budget = body["max_tokens"]
        budgets.append(budget)
        return httpx.Response(400, request=request, json={"error": {
            "message": rejection(budget, 8192 if len(budgets) == 1 else 4096, 1024), "type": "BadRequestError"}})

    with pytest.raises(Exception):
        asyncio.run(exercise(monkeypatch, mode, respond))
    assert budgets == [65535, 7168]


@pytest.mark.parametrize("mode", ["sync", "async"])
def test_generated_output_cannot_change_the_request_budget(monkeypatch, mode):
    calls = []

    def respond(request):
        body = json.loads(request.content)
        calls.append(body["max_tokens"])
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps({"text": [rejection(65535, 8192, 1024)]})}}]})

    with pytest.raises(Exception):
        asyncio.run(exercise(monkeypatch, mode, respond))
    assert calls == [65535]


@pytest.mark.parametrize("mode", ["sync", "async", "raw"])
def test_a_provider_reroute_starts_with_its_own_budget(monkeypatch, mode):
    calls = []

    def respond(request):
        body = json.loads(request.content)
        budget, model = body["max_tokens"], body["model"]
        calls.append((model, budget))
        if model == "local-output-budget":
            if budget == 65535:
                return httpx.Response(400, request=request, json={"error": {"type": "BadRequestError",
                    "message": rejection(budget, 8192, 1024)}})
            return httpx.Response(401, request=request, json={"error": {"type": "authentication_error", "message": "invalid api key"}})
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": model, "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": '{"text":"ready"}'}}]})

    asyncio.run(exercise(monkeypatch, mode, respond, reroute=lambda model, error: LLMConfig(
        model="openai/backup", api_base="http://backup.invalid/v1", max_tokens=4096, structured_output="json_schema")))
    assert calls == [("local-output-budget", 65535), ("local-output-budget", 7168), ("backup", 4096), ("backup", 4096)]


@pytest.mark.parametrize("mode", ["sync", "async", "raw"])
def test_budget_recovery_composes_with_max_completion_tokens_negotiation(monkeypatch, mode):
    monkeypatch.setattr(llm_client, "_REJECTED", {})
    calls = []

    def respond(request):
        body = json.loads(request.content)
        key = "max_tokens" if "max_tokens" in body else "max_completion_tokens"
        calls.append((key, body[key]))
        if key == "max_tokens":
            return httpx.Response(400, request=request, json={"error": {"type": "BadRequestError",
                "message": "Unsupported parameter: 'max_tokens' is not supported; use max_completion_tokens instead"}})
        if body[key] > 7168:
            return httpx.Response(400, request=request, json={"error": {"type": "BadRequestError",
                "message": rejection(body[key], 8192, 1024)}})
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": '{"text":"ready"}'}}]})

    asyncio.run(exercise(monkeypatch, mode, respond))
    assert calls == [("max_tokens", 65535), ("max_completion_tokens", 65535), ("max_completion_tokens", 7168),
                     ("max_completion_tokens", 65535), ("max_completion_tokens", 7168)]


@pytest.mark.parametrize("mode", ["sync", "async"])
def test_customer_style_instructor_retry_wrapper_can_recover_the_budget(monkeypatch, mode):
    calls = []

    def respond(request):
        body = json.loads(request.content)
        calls.append(body["max_tokens"])
        if body["max_tokens"] > 7168:
            return httpx.Response(400, request=request, json={"error": {"type": "BadRequestError",
                "message": rejection(body["max_tokens"], 8192, 1024)}})
        return httpx.Response(200, request=request, json={"id": "offline", "object": "chat.completion", "created": 0,
            "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": '{"text":"ready"}'}}]})

    asyncio.run(exercise(monkeypatch, mode, respond, retries=3))
    assert calls == [65535, 65535, 65535, 7168] * 2


@pytest.mark.parametrize("mode", ["sync", "async", "raw"])
@pytest.mark.parametrize("backup_rejects", [False, True])
def test_a_concurrent_provider_change_does_not_inherit_the_old_output_limit(monkeypatch, mode, backup_rejects):
    from litellm import ModelResponse
    from litellm.exceptions import BadRequestError

    calls = []
    def answer(**kwargs):
        calls.append((kwargs["model"], kwargs["max_tokens"]))
        if len(calls) == 1:
            # Another in-flight assistive request advances the shared client.
            client._use(LLMConfig(model="openai/backup", api_base="http://backup.invalid/v1", max_tokens=4096,
                                  structured_output="json_schema"))
            raise BadRequestError(rejection(65535, 8192, 1024), model="openai/local", llm_provider="openai")
        if backup_rejects:
            raise BadRequestError(rejection(kwargs["max_tokens"], 2048, 1024), model="openai/backup", llm_provider="openai")
        return ModelResponse(model=kwargs["model"], choices=[{"index": 0, "finish_reason": "stop",
            "message": {"role": "assistant", "content": '{"text":"ready"}'}}])

    async def acompletion(**kwargs):
        return answer(**kwargs)

    monkeypatch.setattr(llm_client.litellm, "completion", answer)
    monkeypatch.setattr(llm_client.litellm, "acompletion", acompletion)
    client = llm_client.LiteLLMClient(LLMConfig(model="openai/local", api_base="http://local.invalid/v1",
                                              structured_output="json_schema"))
    def invoke():
        if mode == "sync":
            return client.generate_structured(Answer, "System", "User").text
        if mode == "async":
            return asyncio.run(client.generate_structured_async(Answer, "System", "User")).text
        return asyncio.run(client.generate_text_async("System", "User"))

    if backup_rejects:
        with pytest.raises(Exception) as error:
            invoke()
        assert not isinstance(error.value, AssertionError)
    else:
        assert invoke() == ('{"text":"ready"}' if mode == "raw" else "ready")
    assert calls == [("openai/local", 65535), ("openai/backup", 4096)]
