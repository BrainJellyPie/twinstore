import asyncio
import hashlib
import ipaddress
import json
import logging
import os
import re
import threading
import weakref
from collections.abc import Callable
from contextlib import nullcontext
from pathlib import Path
from typing import cast
from urllib.parse import urlsplit

import instructor
import litellm
from instructor.core.exceptions import IncompleteOutputException, InstructorError
from instructor.core.hooks import Hooks
from litellm.exceptions import APIConnectionError, AuthenticationError, BadRequestError, ContextWindowExceededError
from pydantic import BaseModel, ValidationError

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.types import TokenUsage
from store_emulator.engine.files import replace_file

logger = logging.getLogger(__name__)

# Most providers accept 32-bit seeds; larger values are folded into this range.
_SEED_MOD = 2**31 - 1

# Optional request parameters a model refused (e.g. newer Claude models answer "`temperature` is
# deprecated for this model"). Learned from the provider's error at run time, so a new model needs
# no code change; the call is retried once without the parameter. Servers can expose the same model
# alias with different capabilities, so every learned option belongs to its receiving endpoint.
_REJECTED: dict[tuple[str, str], set[str]] = {}
_REJECTED_LOCK = threading.Lock()
_OPTIONAL_PARAMS = ("temperature", "thinking", "reasoning_effort")
# A model can refuse several of them (GPT-6: max_tokens, then temperature): one retry per lesson.
_ATTEMPTS = len(_OPTIONAL_PARAMS) + 2


def _request_errors(error: BaseException) -> list[BaseException]:
    """Unwrap provider errors without treating generated response text as a server rejection."""
    errors: list[BaseException] = []
    seen: set[int] = set()
    stack = [error]
    while stack:
        current = stack.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        if isinstance(current, (ValidationError, json.JSONDecodeError, IncompleteOutputException)):
            continue
        if isinstance(current, InstructorError):
            # Its string includes completions and validation inputs, not just error messages.
            # Earlier rejections do not describe a later accepted-but-invalid answer or timeout.
            if current.failed_attempts:
                stack.append(current.failed_attempts[-1].exception)
            else:
                stack.extend(e for e in (current.__cause__, current.__context__) if e is not None)
            continue
        stack.extend(e for e in (current.__cause__, current.__context__) if e is not None)
        errors.append(current)
    return errors


def is_context_overflow(error: BaseException) -> bool:
    """Recognize a terminal input-context rejection, preserving the original HTTP status."""
    causes = _request_errors(error)
    if isinstance(error, APIConnectionError) and getattr(error, "llm_provider", None) == "ollama_chat":
        # The native adapter can wrap a real HTTP 400 as a synthetic connection
        # error with status 500. Require the original HTTP response as evidence.
        causes = [cause for cause in causes if not (
            isinstance(cause, APIConnectionError) and getattr(cause, "llm_provider", None) == "ollama_chat"
            and getattr(cause, "response", None) is None)]
        if not any(getattr(getattr(cause, "response", None), "status_code", None) == 400 for cause in causes):
            return False
    elif not isinstance(error, BadRequestError):
        return False
    for cause in causes:
        statuses = (getattr(cause, "status_code", None), getattr(getattr(cause, "response", None), "status_code", None))
        if any(isinstance(status, int) and status != 400 for status in statuses):
            return False
    if isinstance(error, ContextWindowExceededError):
        return True
    # LiteLLM can discard the server's structured error type/body. Accept only
    # concrete llama.cpp/Ollama messages, not generated text mentioning context.
    return re.search(
        r"(?:request \(\d+ tokens\) exceeds the available context size \(\d+ tokens\)"
        r"|input \(\d+ tokens\) is larger than the max context size \(\d+ tokens\)"
        r"|the prompt is longer than the context length currently available to the model; "
        r"shorten the prompt, adjust the context length in settings, or use a model with a longer context length)",
        str(error),
    ) is not None


def _rejected_param(error: BaseException) -> str | None:
    """The optional parameter a provider error says it refused, if any. `max_tokens` is special: newer
    OpenAI models want it renamed to `max_completion_tokens` (see _call_kwargs), not dropped."""
    text = "\n".join(str(e) for e in _request_errors(error)).lower()
    if not any(w in text for w in ("deprecated", "not supported", "unsupported", "does not support", "not allowed")):
        return None
    if "'max_tokens'" in text and "max_completion_tokens" in text:
        return "max_tokens"
    return next((p for p in _OPTIONAL_PARAMS if p in text), None)


def _remaining_output_budget(error: BaseException, sent: dict[str, object]) -> int | None:
    """Some vLLM versions reject an output ceiling instead of clamping it to the remaining context."""
    if isinstance(error, InstructorError):
        if not error.failed_attempts:
            return None
        error = error.failed_attempts[-1].exception
    if not isinstance(error, BadRequestError):
        return None
    requested = sent.get("max_tokens", sent.get("max_completion_tokens"))
    if not isinstance(requested, int) or isinstance(requested, bool):
        return None
    causes = _request_errors(error)
    # LiteLLM may label a context-looking HTTP 403 as a 400 context error; keep
    # the original response/exception status authoritative when it is available.
    for cause in causes:
        statuses = (getattr(cause, "status_code", None), getattr(getattr(cause, "response", None), "status_code", None))
        if any(isinstance(status, int) and status != 400 for status in statuses):
            return None
    match = re.search(
        r"'max_tokens' or 'max_completion_tokens' is too large: (\d+)\. "
        r"This model's maximum context length is (\d+) tokens and your request has (\d+) input tokens",
        str(error),
    )
    if match is None:
        return None
    try:
        reported, context, inputs = (int(value) for value in match.groups())
    except ValueError:
        return None
    remaining = context - inputs
    if reported == requested and 0 < remaining < requested:
        return remaining
    return None


# How to switch thinking off, per model: {"type": "disabled"} unless the provider named another value
# (some newer Claude models refuse "disabled" and say which value to send instead), learned like _REJECTED.
_THINKING_OFF: dict[tuple[str, str], dict[str, str]] = {}


def _thinking_off_hint(error: BaseException) -> dict[str, str] | None:
    text = "\n".join(str(e) for e in _request_errors(error))
    if "thinking" not in text or "instead of" not in text:
        return None
    m = re.search(r'send \\?"thinking\\?":\s*\{\\?"type\\?":\s*\\?"([a-z_]+)\\?"\}', text)
    return {"type": m.group(1)} if m and m.group(1) != "disabled" else None


def _should_retry_without(model: str, error: BaseException, sent: dict[str, object]) -> bool:
    """Remember a refused parameter and say whether the call is worth one retry without it. Calls
    already in flight when another call learned the same thing are retried too."""
    endpoint = sent.get("api_base")
    key = (model, endpoint if isinstance(endpoint, str) else "")
    hint = _thinking_off_hint(error)
    if hint is not None and "thinking" in sent:
        if sent["thinking"] == hint:
            return False
        with _REJECTED_LOCK:
            new = _THINKING_OFF.get(key) != hint
            _THINKING_OFF[key] = hint
        if new:
            logger.info(f"{model}: thinking is switched off with {hint}; retrying")
        return True
    param = _rejected_param(error)
    body = sent.get("extra_body")
    if param is None or (param not in sent and not (isinstance(body, dict) and param in body)):
        return False
    with _REJECTED_LOCK:
        new = param not in _REJECTED.setdefault(key, set())
        _REJECTED[key].add(param)
    if new:
        logger.info(f"{model}: provider rejects `{param}`; retrying without it")
    return True


def _accepts(model: str, param: str, api_base: str | None = None) -> bool:
    return param not in _REJECTED.get((model, api_base or ""), set())


# A provider that turned the API key down (not valid, revoked, missing) will not take it on a retry. Assistive clients
# get a `reroute` from the application: given the model that failed and the error, it sets the key aside and returns
# the next model that can answer (or None, or raises with a message saying what to do).
type Reroute = Callable[[str, BaseException], LLMConfig | None]
_MAX_REROUTES = 3
_AUTH_MARKERS = ("api_key_invalid", "api key not valid", "invalid x-api-key", "incorrect api key", "invalid api key",
                 "invalid_api_key", "authentication_error", "missing anthropic api key", "api key is missing")


def is_auth_error(error: BaseException) -> bool:
    """Whether the provider turned the API key down, looking through the retries Instructor wraps the error in."""
    for e in _request_errors(error):
        if isinstance(e, AuthenticationError) or any(marker in str(e).lower() for marker in _AUTH_MARKERS):
            return True
    return False


def _hash6(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()[:4]


def final_answer_text(content: str) -> str:
    """Remove leading thoughts, including an opening tag prefilled by the server."""
    final = content
    while True:
        stripped = final.lstrip()
        if stripped.startswith("<think>"):
            end = stripped.find("</think>")
            if end < 0:
                return ""  # An unfinished explicit thought has no final answer.
            final = stripped[end + len("</think>"):].lstrip()
        elif stripped.startswith("</think>"):
            final = stripped[len("</think>"):].lstrip()
        else:
            # Some models receive <think> in the prompt and generate only its
            # end. Require a standalone closing line; inline literal tags and
            # escaped line breaks inside JSON strings are ordinary content.
            end = re.search(r"(?m)^[ \t]*</think>[ \t]*(?:\r?\n|$)", stripped)
            if end is None:
                return final
            final = stripped[end.end():].lstrip()


def _final_structured_content(response: object) -> None:
    """Keep reasoning examples out of JSON parsing, including prompt-prefilled thoughts."""
    choices = getattr(response, "choices", None)
    if not isinstance(choices, list):
        return
    for choice in cast(list[object], choices):
        message = getattr(choice, "message", None)
        content = getattr(message, "content", None)
        if isinstance(content, str):
            setattr(message, "content", final_answer_text(content))


def _compact_json_schema_prompt(pretty: str, compact: str, messages: object) -> None:
    """Minify the SDK's exact schema text, leaving its meaning and other messages intact."""
    if not isinstance(messages, list):
        return
    for item in cast(list[object], messages):
        if not isinstance(item, dict):
            continue
        # Instructor's provider kwargs contain untyped mutable message dictionaries.
        message = cast(dict[str, object], item)
        content = message.get("content")
        if message.get("role") == "system" and isinstance(content, str):
            message["content"] = content.replace(pretty, compact)


class LiteLLMClient:

    def __init__(self, config: LLMConfig, *, reroute: Reroute | None = None, max_reroutes: int = _MAX_REROUTES):
        self._reroute = reroute
        self._max_reroutes = max_reroutes
        self._use(config)
        self._usage_lock = threading.Lock()
        self._usage = TokenUsage()

    def _use(self, config: LLMConfig) -> None:
        self.model = config.model
        self.temperature = config.temperature
        self.max_tokens = config.max_tokens
        self.api_base = config.api_base
        if self.model.startswith("ollama_chat/") and self.api_base and not any(c in self.api_base for c in "?#"):
            # The native adapter appends /api/chat without trimming directory
            # slashes; even a trailing slash on the full route duplicates it.
            self.api_base = self.api_base.rstrip("/")
        self.seed = config.seed
        self.timeout_sec = config.timeout_sec
        self.cache_dir = Path(config.cache_dir) if config.cache_dir else None
        self.cache_namespace = config.cache_namespace
        self._api_key = config.api_key.get_secret_value() if config.api_key else None
        self.max_parallel = config.max_parallel
        self._chat_template_thinking = config.chat_template_thinking
        self._structured_sdk_retries = config.structured_sdk_retries
        self._structured_output = config.structured_output
        self._slots: weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Semaphore] = weakref.WeakKeyDictionary()
        mode = instructor.Mode.JSON_SCHEMA if config.structured_output == "json_schema" else instructor.Mode.JSON
        self._client = instructor.from_litellm(litellm.completion, mode=mode)  # type: ignore[reportUnknownMemberType]
        self._async_client = instructor.from_litellm(litellm.acompletion, mode=mode)  # type: ignore[reportUnknownMemberType]
        self._configuration = object()

    def _slots_here(self) -> asyncio.Semaphore | None:
        """The request limit in this event loop (a semaphore belongs to one loop; runs may use several)."""
        if not self.max_parallel:
            return None
        loop = asyncio.get_running_loop()
        slots = self._slots.get(loop)
        if slots is None:
            slots = self._slots[loop] = asyncio.Semaphore(self.max_parallel)
        return slots

    def _move_on(self, tried: str, nxt: LLMConfig | None) -> bool:
        if nxt is None or (nxt.model == tried and nxt.api_base == self.api_base):
            return False
        if self.model == tried:
            logger.warning(f"{tried}: no API key the provider takes; continuing on {nxt.model}")
            self._use(nxt)
        return True

    def _wants_reroute(self, error: BaseException, hops: int) -> bool:
        return self._reroute is not None and hops < self._max_reroutes and is_auth_error(error)

    def _rerouted(self, tried: str, error: BaseException, hops: int, configuration: object) -> bool:
        """Whether to repeat a call the provider refused for its key: on the model another call already moved to, or on
        the next one the application names."""
        if not self._wants_reroute(error, hops) or self._reroute is None:
            return False
        if self._configuration is not configuration:
            return True
        try:
            nxt = self._reroute(tried, error)
        except Exception:
            if self._configuration is not configuration:
                return True
            raise
        if self._configuration is not configuration:
            return True
        return self._move_on(tried, nxt)

    async def _arerouted(self, tried: str, error: BaseException, hops: int, configuration: object) -> bool:
        if not self._wants_reroute(error, hops) or self._reroute is None:
            return False
        if self._configuration is not configuration:
            return True
        # In a thread: finding the next model may wait for the local model to get ready.
        try:
            nxt = await asyncio.to_thread(self._reroute, tried, error)
        except Exception:
            if self._configuration is not configuration:
                return True
            raise
        if self._configuration is not configuration:
            return True
        return self._move_on(tried, nxt)

    def _messages(self, system_prompt: str, user_prompt: str) -> tuple[list[dict[str, str]], str]:
        rid = _hash6(system_prompt + user_prompt)
        logger.info(f"{self.model} [{rid}] req {len(system_prompt) + len(user_prompt):,}chars")
        return [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}], rid

    def _messages_with_image(
        self,
        system_prompt: str,
        user_prompt: str,
        image_url: str,
    ) -> tuple[list[dict[str, object]], str]:
        rid = _hash6(system_prompt + user_prompt)
        logger.info(f"{self.model} [{rid}] req {len(system_prompt) + len(user_prompt):,}chars +image")
        return [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_prompt},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            },
        ], rid

    def _openai_hosted(self) -> bool:
        return self.model.startswith("openai/gpt-") and "api.openai.com" in (self.api_base or "api.openai.com")

    def _is_loopback(self) -> bool:
        if not self.api_base:
            return False
        try:
            host = urlsplit(self.api_base).hostname
            return host in {"localhost", "localhost."} or bool(host and ipaddress.ip_address(host).is_loopback)
        except ValueError:
            return False

    def _compact_schema_text(self, response_model: type[BaseModel]) -> tuple[str, str] | None:
        if self._structured_output != "json" or not self._is_loopback():
            return None
        schema = response_model.model_json_schema()
        pretty = json.dumps(schema, indent=2, ensure_ascii=False)
        # Shortening small schemas can change model decisions without a meaningful
        # context saving; retain their established prompt format.
        if len(pretty) < 4096:
            return None
        return pretty, json.dumps(schema, separators=(",", ":"), ensure_ascii=False)

    def _ollama_direct_answer(self) -> bool:
        # The recommended Qwen3.5 renderer defaults to thinking and supports an
        # explicit false. Other families can require reasoning or named levels.
        if not self.model.startswith("ollama_chat/"):
            return False
        name = self.model.removeprefix("ollama_chat/").casefold()
        if name.endswith((":cloud", "-cloud")) or name.partition(":")[0] not in {
            "qwen3.5", "library/qwen3.5", "registry.ollama.ai/library/qwen3.5",
        }:
            return False
        try:
            return (urlsplit(self.api_base or "").hostname or "").rstrip(".") != "ollama.com"
        except ValueError:
            return False

    def _call_kwargs(self, seed: int | None, max_tokens: int | None = None, *, structured: bool = False) -> dict[str, object]:
        """Provider-agnostic sampling kwargs. Unsupported params are dropped by LiteLLM."""
        kwargs: dict[str, object] = {
            "model": self.model,
            "max_tokens": max_tokens or self.max_tokens,
            "timeout": self.timeout_sec,
            "drop_params": True,
        }
        loopback = self._is_loopback()
        if structured and (loopback or self._structured_sdk_retries is not None):
            # Instructor already owns this call's attempt budget, including
            # named self-hosted servers on another machine.
            kwargs["num_retries"] = self._structured_sdk_retries if self._structured_sdk_retries is not None else 0
        if not _accepts(self.model, "max_tokens", self.api_base):
            kwargs["max_completion_tokens"] = kwargs.pop("max_tokens")
        if _accepts(self.model, "temperature", self.api_base):
            kwargs["temperature"] = self.temperature
        # Claude models may think before answering (adaptive thinking), which can use up a small
        # max_tokens budget before any JSON is written. Shopper decisions are short: answer directly.
        if self.model.startswith("anthropic/") and _accepts(self.model, "thinking", self.api_base):
            kwargs["thinking"] = _THINKING_OFF.get((self.model, self.api_base or ""), {"type": "disabled"})
        # Hybrid Qwen models on Model Studio think by default (billed reasoning tokens, slower);
        # the OpenAI-compatible endpoint takes the switch as a top-level body field.
        if self.model.startswith("openai/qwen") and "aliyuncs.com" in (self.api_base or ""):
            kwargs["extra_body"] = {"enable_thinking": False}
        # OpenAI reasoning models (GPT-6 Luna) reason by default, and the reasoning tokens count
        # against max_completion_tokens: a 160-token glance budget was used up before any JSON, so
        # most glances failed. A model that refuses the switch is remembered and asked without it.
        if self._openai_hosted() and _accepts(self.model, "reasoning_effort", self.api_base):
            kwargs["extra_body"] = {"reasoning_effort": "none"}
        if self._chat_template_thinking is not None:
            # Self-hosted hybrid models otherwise spend short answer budgets on
            # reasoning before their JSON. Only known template-capable providers opt in.
            kwargs["extra_body"] = {"chat_template_kwargs": {"enable_thinking": self._chat_template_thinking}}
        if self.model.startswith("ollama_chat/"):
            # Preserve requirements both when loading input and when generation
            # fills the context, so oversized tasks can recover explicitly.
            body = cast(dict[str, object], kwargs.setdefault("extra_body", {}))
            body.update(truncate=False, shift=False)
            if self._ollama_direct_answer():
                body["think"] = False
        if self.api_base:
            kwargs["api_base"] = self.api_base
            # Local OpenAI-compatible servers (llama.cpp, vLLM) usually need no key, but the OpenAI
            # SDK refuses to send a request without one.
            local_key = os.environ.get("PARASTORE_LOCAL_API_KEY", "").strip()
            if self.model.startswith("openai/") and (loopback and local_key or not os.environ.get("OPENAI_API_KEY")):
                kwargs["api_key"] = local_key or "not-needed"
        if self._api_key:
            kwargs["api_key"] = self._api_key
        effective = self._effective_seed(seed)
        if effective is not None:
            kwargs["seed"] = effective
        return kwargs

    def _effective_seed(self, seed: int | None) -> int | None:
        """Per-call seeds are only sent when seeding is enabled in the config."""
        if self.seed is None:
            return None
        if seed is None:
            return self.seed % _SEED_MOD
        return (self.seed * 1_000_003 + seed) % _SEED_MOD

    def _accumulate_usage(self, raw_response: object, rid: str, *, requests: int = 1, failed: bool = False) -> None:
        usage = getattr(raw_response, "total_usage" if failed else "usage", None)
        with self._usage_lock:
            self._usage.requests += requests
        if usage is None:
            return
        prompt = getattr(usage, "prompt_tokens", 0) or 0
        completion = getattr(usage, "completion_tokens", 0) or 0
        total = getattr(usage, "total_tokens", 0) or 0
        logger.info(f"{self.model} [{rid}] in={prompt} out={completion}")

        with self._usage_lock:
            self._usage.prompt_tokens += prompt
            self._usage.completion_tokens += completion
            self._usage.total_tokens += total

    def get_usage(self) -> TokenUsage:
        with self._usage_lock:
            return self._usage.model_copy()

    def reset_usage(self) -> None:
        with self._usage_lock:
            self._usage = TokenUsage()

    # ── response cache ────────────────────────────────────────────────
    # Content-addressed: identical (model, sampling params, seed, output mode, schema, prompts) → identical
    # response. Makes reruns free, keeps paired experiments exact, and survives crashes.

    def _cache_path(
        self, response_model: type[BaseModel], messages: object, seed: int | None, max_tokens: int | None = None,
    ) -> Path | None:
        if self.cache_dir is None:
            return None
        extra: dict[str, str] = {"reasoning": "none"} if self._openai_hosted() else {}
        if self._compact_schema_text(response_model) is not None:
            extra["json_schema_prompt"] = "compact-v1"
        if self.model.startswith("ollama_chat/"):
            # Older SDKs accepted native length cutoffs as successful replies.
            extra["ollama_finish_reason"] = "native-v1"
            extra["ollama_context"] = "preserve-context-v2"
            if self._ollama_direct_answer():
                extra["ollama_thinking"] = "false"
        if self._chat_template_thinking is not None:
            extra["chat_template_thinking"] = str(self._chat_template_thinking)
        if self.seed is None and seed is not None:
            # A per-respondent draw still has an identity when provider seeding
            # is disabled. Keep it separate without sending a seed to the API.
            extra["request_seed"] = str(seed)
        if self.cache_namespace:
            extra["cache_namespace"] = self.cache_namespace
        key_src = json.dumps(
            {
                **extra,
                "structured_parser": "final-think-v2",
                "structured_output": self._structured_output,
                "model": self.model,
                # Two local servers often share a placeholder model id; the endpoint tells them apart.
                "api_base": self.api_base or "",
                "temperature": self.temperature,
                "max_tokens": max_tokens or self.max_tokens,
                "seed": self._effective_seed(seed),
                "schema": response_model.model_json_schema(),
                "messages": messages,
            },
            sort_keys=True, ensure_ascii=False,
        )
        key = hashlib.sha256(key_src.encode()).hexdigest()
        return self.cache_dir / key[:2] / f"{key}.json"

    def _cache_get[T: BaseModel](self, path: Path | None, response_model: type[T]) -> T | None:
        if path is None:
            return None
        try:
            data: object = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("expected a cache entry object")
            # Match Instructor's strict JSON validation, including JSON arrays
            # for tuple fields. Cache reuse must not add numeric/type coercions.
            result = response_model.model_validate_json(
                json.dumps(cast(dict[str, object], data)["result"]), strict=True)
        except FileNotFoundError:
            return None
        except (OSError, ValueError, KeyError) as e:
            logger.warning(f"[llm-cache] ignoring unreadable entry {path.name}: {e}")
            return None
        with self._usage_lock:
            self._usage.requests += 1
            self._usage.cached_requests += 1
        return result

    def _cache_put(self, path: Path | None, result: BaseModel) -> None:
        if path is None:
            return
        tmp = path.with_suffix(f".{os.getpid()}.{threading.get_ident()}.tmp")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(json.dumps({"result": result.model_dump(mode="json")}, ensure_ascii=False), encoding="utf-8")
            replace_file(tmp, path)
        except OSError as e:
            # Caching is optional; a full or read-only cache must not discard a valid model answer.
            logger.warning(f"[llm-cache] could not cache response {path.name}: {e}")
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass  # The same storage failure may also prevent removing a partial write.

    def _create(self, response_model: type[BaseModel], msgs: object, max_retries: int,
                seed: int | None, max_tokens: int | None = None) -> tuple[object, object]:
        budget, adjusted = max_tokens, False
        budget_configuration = self._configuration
        for attempt in range(_ATTEMPTS + 1):
            if self._configuration is not budget_configuration:
                budget = max_tokens
                budget_configuration = self._configuration
            kwargs = self._call_kwargs(seed, budget, structured=True)
            calls = 0
            schema_text = self._compact_schema_text(response_model)

            def request_started(*_args: object, **request_kwargs: object) -> None:
                nonlocal calls
                calls += 1
                if schema_text is not None:
                    _compact_json_schema_prompt(*schema_text, request_kwargs.get("messages"))

            hooks = Hooks()
            hooks.on("completion:kwargs", request_started)
            hooks.on("completion:response", _final_structured_content)
            try:
                result = self._client.chat.completions.create_with_completion(  # type: ignore[reportUnknownMemberType]
                    response_model=response_model,
                    messages=msgs,  # type: ignore[reportArgumentType]
                    max_retries=max_retries,
                    hooks=hooks,
                    **kwargs,  # type: ignore[reportArgumentType]  # LiteLLM kwargs are untyped
                )
                with self._usage_lock:
                    self._usage.requests += max(0, calls - 1)  # The successful completion is recorded by _generate.
                return result
            except Exception as e:
                self._accumulate_usage(e, response_model.__name__, requests=calls, failed=True)
                remaining = None if adjusted else _remaining_output_budget(e, kwargs)
                if remaining is not None:
                    budget, adjusted = remaining, True
                    logger.info("%s: retrying with the server's remaining %s output tokens", kwargs["model"], remaining)
                    continue
                if attempt - int(adjusted) < _ATTEMPTS - 1 and _should_retry_without(str(kwargs["model"]), e, kwargs):
                    continue
                raise
        raise AssertionError("unreachable")

    async def _acreate(self, response_model: type[BaseModel], msgs: object, max_retries: int,
                       seed: int | None, max_tokens: int | None = None) -> tuple[object, object]:
        budget, adjusted = max_tokens, False
        initial_configuration = budget_configuration = self._configuration
        attempt = 0
        while attempt < _ATTEMPTS + 1:
            configuration = self._configuration
            # _agenerate already holds the initial endpoint's slot. A late option/budget
            # rejection can retry on a different endpoint, whose capacity is independent.
            slots = self._slots_here() if configuration is not initial_configuration else None
            async with slots if slots is not None else nullcontext():
                if configuration is not self._configuration:
                    continue  # A queued transition sent no request and consumes no retry.
                if configuration is not budget_configuration:
                    budget = max_tokens
                    budget_configuration = configuration
                kwargs = self._call_kwargs(seed, budget, structured=True)
                calls = 0
                schema_text = self._compact_schema_text(response_model)

                def request_started(*_args: object, **request_kwargs: object) -> None:
                    nonlocal calls
                    calls += 1
                    if schema_text is not None:
                        _compact_json_schema_prompt(*schema_text, request_kwargs.get("messages"))

                hooks = Hooks()
                hooks.on("completion:kwargs", request_started)
                hooks.on("completion:response", _final_structured_content)
                try:
                    result = await self._async_client.chat.completions.create_with_completion(  # type: ignore[reportUnknownMemberType]
                        response_model=response_model,
                        messages=msgs,  # type: ignore[reportArgumentType]
                        max_retries=max_retries,
                        hooks=hooks,
                        **kwargs,  # type: ignore[reportArgumentType]  # LiteLLM kwargs are untyped
                    )
                    with self._usage_lock:
                        self._usage.requests += max(0, calls - 1)  # The successful completion is recorded by _agenerate.
                    return result
                except Exception as e:
                    self._accumulate_usage(e, response_model.__name__, requests=calls, failed=True)
                    remaining = None if adjusted else _remaining_output_budget(e, kwargs)
                    if remaining is not None:
                        budget, adjusted = remaining, True
                        logger.info("%s: retrying with the server's remaining %s output tokens", kwargs["model"], remaining)
                        attempt += 1
                        continue
                    if attempt - int(adjusted) < _ATTEMPTS - 1 and _should_retry_without(str(kwargs["model"]), e, kwargs):
                        attempt += 1
                        continue
                    raise
        raise AssertionError("unreachable")

    def _generate[T: BaseModel](self, response_model: type[T], msgs: object, rid: str, max_retries: int,
                                seed: int | None, max_tokens: int | None = None) -> T:
        hops = 0
        while True:
            configuration = self._configuration
            cache_path = self._cache_path(response_model, msgs, seed, max_tokens)
            cached = self._cache_get(cache_path, response_model)
            if cached is not None:
                return cached
            tried = self.model
            try:
                model, raw = self._create(response_model, msgs, max_retries, seed, max_tokens)
            except Exception as e:
                if self._rerouted(tried, e, hops, configuration):
                    hops += 1
                    continue
                raise
            self._accumulate_usage(raw, rid)
            if configuration is self._configuration:
                self._cache_put(cache_path, model)  # type: ignore[reportArgumentType]
            return model  # type: ignore[reportReturnType]

    async def _agenerate[T: BaseModel](self, response_model: type[T], msgs: object, rid: str, max_retries: int,
                                       seed: int | None, max_tokens: int | None = None) -> T:
        hops = 0
        while True:
            configuration = self._configuration
            cache_path = self._cache_path(response_model, msgs, seed, max_tokens)
            cached = self._cache_get(cache_path, response_model)
            if cached is not None:
                return cached
            tried, slots = self.model, self._slots_here()
            try:
                if slots is None:
                    model, raw = await self._acreate(response_model, msgs, max_retries, seed, max_tokens)
                else:
                    async with slots:
                        # Another request may have changed provider while this one queued.
                        # Recompute its cache identity and use the new provider's semaphore.
                        if configuration is not self._configuration:
                            continue
                        model, raw = await self._acreate(response_model, msgs, max_retries, seed, max_tokens)
            except Exception as e:
                if await self._arerouted(tried, e, hops, configuration):
                    hops += 1
                    continue
                raise
            self._accumulate_usage(raw, rid)
            if configuration is self._configuration:
                self._cache_put(cache_path, model)  # type: ignore[reportArgumentType]
            return model  # type: ignore[reportReturnType]

    def generate_structured[T: BaseModel](
        self,
        response_model: type[T],
        system_prompt: str,
        user_prompt: str,
        *,
        max_retries: int = 1,
        seed: int | None = None,
        route: str | None = None,
    ) -> T:
        msgs, rid = self._messages(system_prompt, user_prompt)
        return self._generate(response_model, msgs, rid, max_retries, seed)

    async def generate_structured_async[T: BaseModel](
        self,
        response_model: type[T],
        system_prompt: str,
        user_prompt: str,
        *,
        max_retries: int = 1,
        seed: int | None = None,
        route: str | None = None,
        max_tokens: int | None = None,
    ) -> T:
        msgs, rid = self._messages(system_prompt, user_prompt)
        return await self._agenerate(response_model, msgs, rid, max_retries, seed, max_tokens)

    def generate_structured_with_image[T: BaseModel](
        self,
        response_model: type[T],
        system_prompt: str,
        user_prompt: str,
        image_url: str,
        *,
        max_retries: int = 1,
        seed: int | None = None,
        route: str | None = None,
    ) -> T:
        msgs, rid = self._messages_with_image(system_prompt, user_prompt, image_url)
        return self._generate(response_model, msgs, rid, max_retries, seed)

    async def generate_structured_with_image_async[T: BaseModel](
        self,
        response_model: type[T],
        system_prompt: str,
        user_prompt: str,
        image_url: str,
        *,
        max_retries: int = 1,
        seed: int | None = None,
        route: str | None = None,
        max_tokens: int | None = None,
    ) -> T:
        msgs, rid = self._messages_with_image(system_prompt, user_prompt, image_url)
        return await self._agenerate(response_model, msgs, rid, max_retries, seed, max_tokens)

    async def generate_text_async(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        enable_search: bool = False,
        route: str | None = None,
    ) -> str:
        """Bypass Instructor — raw text completion. Use when the schema varies by
        category and we need ad-hoc JSON output.

        enable_search=True enables the Gemini Search Grounding tool
        (Phase 0 spike confirmed `tools=[{"google_search": {}}]` works).
        Non-Gemini models may ignore it or raise BadRequest — caller must branch.
        """
        msgs, rid = self._messages(system_prompt, user_prompt)
        raw: object = None
        attempt = hops = 0
        budget: int | None = None
        adjusted = False
        budget_configuration = self._configuration
        while True:
            configuration = self._configuration
            if configuration is not budget_configuration:
                budget = None
                budget_configuration = configuration
            kwargs: dict[str, object] = {"messages": msgs, **self._call_kwargs(None, budget)}
            if enable_search:
                kwargs["tools"] = [{"google_search": {}}]
            tried, slots = self.model, self._slots_here()
            try:
                if slots is None:
                    raw = await litellm.acompletion(**kwargs)  # type: ignore[reportUnknownMemberType]
                else:
                    async with slots:
                        if configuration is not self._configuration:
                            continue
                        raw = await litellm.acompletion(**kwargs)  # type: ignore[reportUnknownMemberType]
                break
            except Exception as e:
                remaining = None if adjusted else _remaining_output_budget(e, kwargs)
                if remaining is not None:
                    budget, adjusted = remaining, True
                    logger.info("%s: retrying with the server's remaining %s output tokens", kwargs["model"], remaining)
                    continue
                if attempt < _ATTEMPTS - 1 and _should_retry_without(str(kwargs["model"]), e, kwargs):
                    attempt += 1
                    continue
                if await self._arerouted(tried, e, hops, configuration):
                    hops += 1
                    budget, adjusted, attempt = None, False, 0
                    continue
                raise
        self._accumulate_usage(raw, rid)
        choices: list[object] = list(getattr(raw, "choices", None) or [])
        if not choices:
            return ""
        first: object = choices[0]
        if getattr(first, "finish_reason", None) == "length":
            # Free-text summaries are evidence too; a cutoff is not a final answer.
            raise IncompleteOutputException(last_completion=raw)
        msg: object = getattr(first, "message", None)
        return str(getattr(msg, "content", "") or "")
