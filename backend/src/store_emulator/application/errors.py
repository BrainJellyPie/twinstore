from typing import overload


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
    (("max_tokens length limit", "output is incomplete", "finish_reason='length'"),
     "the model's reply was cut off before it finished. Try again, or pick another model."),
    (("validation error", "instructorretryexception", "jsondecodeerror"),
     "the model's reply was not in the expected form. Try again, or pick another model."),
)


def model_failure(error: BaseException, what: str) -> str:
    """A failed model call in words a user can act on; the raw error belongs in the server log."""
    text = f"{type(error).__name__}: {error}".casefold()
    for needles, hint in _MODEL_FAILURES:
        if any(n in text for n in needles):
            return f"{what}: {hint}"
    return f"{what} ({type(error).__name__}): {str(error)[:200]}"
