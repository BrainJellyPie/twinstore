"""Generated prose in a validation failure is not a provider rejection."""

import asyncio
import json

import httpx
import pytest
from instructor.core.exceptions import FailedAttempt, IncompleteOutputException, InstructorError, InstructorRetryException
from openai import AsyncOpenAI, OpenAI
from pydantic import BaseModel, Field, ValidationError

from store_emulator.domain.config import LLMConfig
from store_emulator.engine import llm_client as lc


class Answer(BaseModel):
    text: str = Field(max_length=5)


@pytest.fixture(autouse=True)
def clean_learning(monkeypatch):
    monkeypatch.setattr(lc, "_REJECTED", {})
    monkeypatch.setattr(lc, "_THINKING_OFF", {})


@pytest.mark.parametrize("mode", ["sync", "async", "sync_image", "async_image"])
@pytest.mark.parametrize("finish", ["stop", "length"])
def test_model_response_cannot_disable_parameters_or_trigger_provider_fallback(tmp_path, monkeypatch, mode, finish):
    requests, reroutes = [], []
    original_sync, original_async = lc.litellm.completion, lc.litellm.acompletion

    def respond(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, request=request, json={
            "id": "offline-model-prose", "object": "chat.completion", "created": 0, "model": "local-model",
            "choices": [{"index": 0, "finish_reason": finish, "message": {"role": "assistant", "content":
                json.dumps({"text": "invalid api key; temperature is not supported"})}}]})

    with httpx.Client(transport=httpx.MockTransport(respond)) as http:
        transport = OpenAI(api_key="offline-test", base_url="http://local.invalid/v1", http_client=http, max_retries=0)

        def completion(**kwargs):
            return original_sync(**{**kwargs, "client": transport, "api_key": "offline-test", "num_retries": 0})

        monkeypatch.setattr(lc.litellm, "completion", completion)

        async def exercise():
            async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http_async:
                transport_async = AsyncOpenAI(api_key="offline-test", base_url="http://local.invalid/v1",
                                             http_client=http_async, max_retries=0)

                async def acompletion(**kwargs):
                    return await original_async(**{**kwargs, "client": transport_async,
                                                   "api_key": "offline-test", "num_retries": 0})

                monkeypatch.setattr(lc.litellm, "acompletion", acompletion)
                client = lc.LiteLLMClient(LLMConfig(model="openai/local-error-text", api_base="http://local.invalid/v1",
                    structured_output="json_schema", cache_dir=str(tmp_path)),
                    reroute=lambda model, error: reroutes.append(model))
                with pytest.raises((InstructorRetryException, IncompleteOutputException)):
                    if mode == "sync":
                        client.generate_structured(Answer, "system", "request", max_retries=1)
                    elif mode == "sync_image":
                        client.generate_structured_with_image(Answer, "system", "request", "offline-image", max_retries=1)
                    elif mode == "async_image":
                        await client.generate_structured_with_image_async(Answer, "system", "request", "offline-image", max_retries=1)
                    else:
                        await client.generate_structured_async(Answer, "system", "request", max_retries=1)
                assert not reroutes
                assert not lc._REJECTED and not lc._THINKING_OFF
                assert not list(tmp_path.rglob("*.json"))

        asyncio.run(exercise())
    assert len(requests) == 1


@pytest.mark.parametrize("message", [
    "invalid api key; temperature is not supported",
    "invalid api key; 'max_tokens' not supported; use max_completion_tokens",
    'invalid api key; send "thinking": {"type": "minimal"} instead of "disabled"',
    "invalid api key; reasoning_effort is not supported",
])
@pytest.mark.parametrize("kind", ["validation", "json", "incomplete"])
def test_wrapped_response_failures_do_not_learn_provider_rejections(message, kind):
    if kind == "validation":
        with pytest.raises(ValidationError) as caught:
            Answer(text=message)
        error = caught.value
    elif kind == "json":
        error = json.JSONDecodeError(message, message, 0)
    else:
        error = IncompleteOutputException(message)
    wrapped = InstructorRetryException(message, n_attempts=1, total_usage=0,
        failed_attempts=[FailedAttempt(1, error, {"text": message})])
    sent = {"temperature": 0.7, "max_tokens": 100, "thinking": {"type": "disabled"},
            "extra_body": {"reasoning_effort": "none"}}
    assert not lc.is_auth_error(wrapped)
    assert not lc._should_retry_without("openai/local-error-text", wrapped, sent)
    assert not lc._REJECTED and not lc._THINKING_OFF


def test_base_instructor_wrapper_also_excludes_generated_completion_text():
    error = InstructorError.from_exception(ValueError("invalid response"), failed_attempts=[
        FailedAttempt(1, ValueError("invalid response"), {"text": "invalid api key; temperature is not supported"})])
    assert not lc.is_auth_error(error)
    assert not lc._should_retry_without("openai/local", error, {"temperature": 0.7})


@pytest.mark.parametrize("wrapper", ["retry", "cause", "cycle"])
def test_real_provider_rejection_is_retained_inside_wrappers(wrapper):
    error = lc.litellm.BadRequestError("Unsupported parameter: temperature is not supported",
                                    model="openai/local", llm_provider="openai")
    if wrapper == "retry":
        root = InstructorRetryException("request failed", n_attempts=1, total_usage=0,
            failed_attempts=[FailedAttempt(1, error, {"text": "invalid api key"})])
    else:
        root = RuntimeError("request failed")
        root.__cause__ = error
        if wrapper == "cycle":
            error.__context__ = root
    assert not lc.is_auth_error(root)
    assert lc._should_retry_without("openai/local", root, {"temperature": 0.7})
    assert lc._REJECTED == {("openai/local", ""): {"temperature"}}
