"""Recovery advice follows the final failure and the native server's real response."""

import asyncio
import json

import pytest
from instructor.core.exceptions import FailedAttempt, IncompleteOutputException, InstructorRetryException
from pydantic import BaseModel, Field, ValidationError

from store_emulator.application.errors import model_failure
from store_emulator.domain.config import LLMConfig
from store_emulator.engine.llm_client import LiteLLMClient
from tests.engine.test_ollama_input_context import TOO_LONG, native_http


class Reply(BaseModel):
    text: str = Field(max_length=5)


@pytest.mark.parametrize("status,message,hint", [
    (400, TOO_LONG, "context"),
    (400, "this model does not support images", "rejected the request"),
    (401, "unauthorized", "rejected the API key"),
    (403, "forbidden", "denied access"),
    (404, "model 'qwen3.5:2b' not found, try pulling it first", "model or endpoint"),
    (429, "overloaded", "limiting requests"),
    (500, "model runner has unexpectedly stopped", "server could not complete"),
    (503, "service unavailable", "server could not complete"),
])
def test_native_server_errors_do_not_tell_users_the_server_was_unreachable(native_http, status, message, hint):
    native_http(lambda body: (status, message))
    client = LiteLLMClient(LLMConfig(model="ollama_chat/local-advice", api_base="http://127.0.0.1:11434", structured_output="json_schema"))
    with pytest.raises(InstructorRetryException) as caught:
        asyncio.run(client.generate_structured_async(Reply, "Reply", "Hello", max_retries=1))
    result = model_failure(caught.value, "Customer generation failed")
    assert result.startswith("Customer generation failed: ") and hint in result
    assert "could not be reached" not in result


@pytest.mark.parametrize("previous", ["invalid api key", "APIConnectionError: connection refused", "rate limit"])
@pytest.mark.parametrize("final,hint", [("validation", "not in the expected form"), ("json", "not in the expected form"),
    ("length", "cut off before it finished"), ("timeout", "took too long")])
def test_advice_ignores_earlier_attempts_and_generated_rejection_text(previous, final, hint):
    if final == "validation":
        with pytest.raises(ValidationError) as caught:
            Reply(text="invalid api key; connection refused; rate limit")
        error = caught.value
    elif final == "json":
        error = json.JSONDecodeError("invalid api key", "invalid api key", 0)
    elif final == "length":
        error = IncompleteOutputException(last_completion={"text": "invalid api key"})
    else:
        error = TimeoutError("timed out")
    wrapped = InstructorRetryException("invalid api key", n_attempts=2, total_usage=0, failed_attempts=[
        FailedAttempt(1, RuntimeError(previous)), FailedAttempt(2, error, {"text": "invalid api key"})])
    assert hint in model_failure(wrapped, "Customer generation failed")


@pytest.mark.parametrize("final", ["validation", "json", "length"])
def test_unwrapped_model_output_is_not_misdiagnosed_as_authentication(final):
    if final == "validation":
        with pytest.raises(ValidationError) as caught:
            Reply(text="invalid api key")
        error = caught.value
    elif final == "json":
        error = json.JSONDecodeError("invalid api key", "invalid api key", 0)
    else:
        error = IncompleteOutputException(message="invalid api key")
    assert "rejected the API key" not in model_failure(error, "Customer generation failed")
