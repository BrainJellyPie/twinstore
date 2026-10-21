"""Failed model calls reach the user as a sentence they can act on."""

import pytest

from store_emulator.application.errors import model_failure


class AuthenticationError(Exception):
    pass


class RateLimitError(Exception):
    pass


class InstructorRetryException(Exception):
    pass


@pytest.mark.parametrize(("error", "expected"), [
    (AuthenticationError("GeminiException - API key not valid"), "rejected the API key"),
    (RateLimitError("429"), "limiting requests"),
    (TimeoutError("read timed out"), "took too long"),
    (InstructorRetryException("1 validation error for ShopperReply"), "not in the expected form"),
    (InstructorRetryException("The output is incomplete due to a max_tokens length limit."), "cut off before it finished"),
])
def test_known_failures_become_advice(error, expected):
    message = model_failure(error, "The shopper could not answer")
    assert message.startswith("The shopper could not answer: ") and expected in message
    assert "Exception" not in message


def test_unknown_failures_keep_a_short_cause():
    message = model_failure(RuntimeError("provider down " + "x" * 400), "No answer")
    assert message.startswith("No answer (RuntimeError): provider down") and len(message) < 240
