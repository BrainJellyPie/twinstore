import json
from typing import overload

from instructor.core.exceptions import IncompleteOutputException, InstructorError
from litellm.exceptions import APIConnectionError
from pydantic import ValidationError

from store_emulator.engine.llm_client import is_context_overflow


class AppError(Exception):
    """Business-rule violation. Supports two call shapes:

    - Legacy: ``AppError(message, status_code=400)`` — code/reason default.
    - spec rev 4 §4.1: ``AppError(status_code, code, reason, message, details=None)``.

    Attributes:
        status_code: HTTP status code.
        code: stable identifier (e.g. "setup_not_found", "racks_locked").
        reason: category (e.g. "not_found", "items_exist").
        message: user-facing message.
        details: structured context.
    """

    status_code: int
    code: str
    reason: str
    message: str
    details: dict[str, object]

    @overload
    def __init__(self, message: str, status_code: int = 400, /) -> None: ...

    @overload
    def __init__(
        self,
        status_code: int,
        code: str,
        reason: str,
        message: str,
        details: dict[str, object] | None = None,
        /,
    ) -> None: ...

    def __init__(  # type: ignore[misc]
        self,
        first: int | str,
        second: str | int = 400,
        reason: str | None = None,
        message: str = "",
        details: dict[str, object] | None = None,
    ) -> None:
        if isinstance(first, str):
            self.message = first
            self.status_code = second if isinstance(second, int) else 400
            self.code = "app_error"
            self.reason = "error"
            self.details = {}
        else:
            if not isinstance(second, str):
                raise TypeError("code must be str when status_code is int")
            if reason is None:
                raise TypeError("reason required for 5-arg form")
            self.status_code = first
            self.code = second
            self.reason = reason
            self.message = message
            self.details = details if details is not None else {}
        super().__init__(self.message)


_MODEL_FAILURES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("authenticationerror", "api key not valid", "invalid api key", "incorrect api key", "invalid x-api-key"),
     "the provider rejected the API key. Check it in Settings → Model providers, or pick another model."),
    (("ratelimiterror", "rate limit", "too many requests"),
     "the provider is limiting requests right now. Wait a moment and try again."),
    (("timeout", "timed out"), "the model took too long to reply. Try again."),
    (("notfounderror", "model not found", "does not exist"), "the provider does not offer this model. Pick another one."),
    (("apiconnectionerror", "connection error", "connection refused", "cannot connect", "connect call failed"),
     ("the model could not be reached. If it is the local model, start it in Settings → Model providers; otherwise "
      "check the connection, or pick another model.")),
    (("max_tokens length limit", "output is incomplete", "finish_reason='length'"),
     "the model's reply was cut off before it finished. Try again, or pick another model."),
    (("repeated the question",), "the model repeated the question instead of answering. Ask again, or pick a larger model."),
    (("validation error", "instructorretryexception", "jsondecodeerror"),
     "the model's reply was not in the expected form. Try again, or pick another model."),
)


def model_failure(error: BaseException, what: str) -> str:
    """A failed model call in words a user can act on; the raw error belongs in the server log."""
    seen: set[int] = set()
    while isinstance(error, InstructorError) and not isinstance(error, IncompleteOutputException) and id(error) not in seen:
        seen.add(id(error))
        if error.failed_attempts:
            error = error.failed_attempts[-1].exception
        elif error.__cause__ is not None:
            error = error.__cause__
        else:
            break
    if is_context_overflow(error):
        return f"{what}: the request exceeds the model's context limit. Shorten the input or use a model with a larger context."
    if isinstance(error, IncompleteOutputException):
        text = "output is incomplete"
    elif isinstance(error, (ValidationError, json.JSONDecodeError, InstructorError)):
        # Validation inputs and prior completions are model output, not evidence
        # that the server rejected a key or lost its connection.
        text = "validation error"
    else:
        text = f"{type(error).__name__}: {error}".casefold()
    if isinstance(error, APIConnectionError) and getattr(error, "llm_provider", None) == "ollama_chat":
        # This SDK adapter wraps native HTTP errors as connection failures.
        original = error.__cause__ or error.__context__
        status = getattr(getattr(original, "response", None), "status_code", None)
        if status == 401:
            text = "authenticationerror"
        elif status == 429:
            text = "ratelimiterror"
        elif status == 403:
            return f"{what}: the server denied access. Check this model's access permissions and credentials."
        elif status == 404:
            return f"{what}: the model or endpoint was not found. Check the server address and that the model is installed."
        elif status == 400:
            return f"{what}: the server rejected the request. Check that this model supports the requested input and settings."
        elif isinstance(status, int) and status >= 500:
            return f"{what}: the model server could not complete the request. Check its status and available resources, then try again."
    for needles, hint in _MODEL_FAILURES:
        if any(n in text for n in needles):
            return f"{what}: {hint}"
    return f"{what} ({type(error).__name__}): {str(error)[:200]}"


def job_failure(error: BaseException, what: str) -> str:
    """The error a failed background job shows: the app's own messages as they are, anything else (a provider's
    error, a library's) in words a user can act on via model_failure. The raw error belongs in the server log."""
    if isinstance(error, (ValueError, AppError)):
        return str(error)[:500]
    return model_failure(error, what)[:500]
