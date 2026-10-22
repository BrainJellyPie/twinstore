import hashlib
import json
import logging
import os
import re
import threading
from pathlib import Path

import instructor
import litellm
from pydantic import BaseModel

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.types import TokenUsage
from store_emulator.engine.files import replace_file

logger = logging.getLogger(__name__)

# Most providers accept 32-bit seeds; larger values are folded into this range.
_SEED_MOD = 2**31 - 1

# Optional request parameters a model refused (e.g. newer Claude models answer "`temperature` is
# deprecated for this model"). Learned from the provider's error at run time, so a new model needs
# no code change; the call is retried once without the parameter.
_REJECTED: dict[str, set[str]] = {}
_REJECTED_LOCK = threading.Lock()
_OPTIONAL_PARAMS = ("temperature", "thinking", "reasoning_effort")
# A model can refuse several of them (GPT-6: max_tokens, then temperature): one retry per lesson.
_ATTEMPTS = len(_OPTIONAL_PARAMS) + 2


def _rejected_param(error: BaseException) -> str | None:
    """The optional parameter a provider error says it refused, if any. `max_tokens` is special: newer
    OpenAI models want it renamed to `max_completion_tokens` (see _call_kwargs), not dropped."""
    text = str(error).lower()
    if not any(w in text for w in ("deprecated", "not supported", "unsupported", "does not support", "not allowed")):
        return None
    if "'max_tokens'" in text and "max_completion_tokens" in text:
        return "max_tokens"
    return next((p for p in _OPTIONAL_PARAMS if p in text), None)


# How to switch thinking off, per model: {"type": "disabled"} unless the provider named another value
# (some newer Claude models refuse "disabled" and say which value to send instead), learned like _REJECTED.
_THINKING_OFF: dict[str, dict[str, str]] = {}


def _thinking_off_hint(error: BaseException) -> dict[str, str] | None:
    text = str(error)
    if "thinking" not in text or "instead of" not in text:
        return None
    m = re.search(r'send \\?"thinking\\?":\s*\{\\?"type\\?":\s*\\?"([a-z_]+)\\?"\}', text)
    return {"type": m.group(1)} if m and m.group(1) != "disabled" else None


def _should_retry_without(model: str, error: BaseException, sent: dict[str, object]) -> bool:
    """Remember a refused parameter and say whether the call is worth one retry without it. Calls
    already in flight when another call learned the same thing are retried too."""
    hint = _thinking_off_hint(error)
    if hint is not None and "thinking" in sent:
        if sent["thinking"] == hint:
            return False
        with _REJECTED_LOCK:
            new = _THINKING_OFF.get(model) != hint
            _THINKING_OFF[model] = hint
        if new:
            logger.info(f"{model}: thinking is switched off with {hint}; retrying")
        return True
    param = _rejected_param(error)
    body = sent.get("extra_body")
    if param is None or (param not in sent and not (isinstance(body, dict) and param in body)):
        return False
    with _REJECTED_LOCK:
        new = param not in _REJECTED.setdefault(model, set())
        _REJECTED[model].add(param)
    if new:
        logger.info(f"{model}: provider rejects `{param}`; retrying without it")
    return True


def _accepts(model: str, param: str) -> bool:
    return param not in _REJECTED.get(model, set())


def _hash6(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()[:4]


class LiteLLMClient:

    def __init__(self, config: LLMConfig):
        self.model = config.model
        self.temperature = config.temperature
        self.max_tokens = config.max_tokens
        self.api_base = config.api_base
        self.seed = config.seed
        self.timeout_sec = config.timeout_sec
        self.cache_dir = Path(config.cache_dir) if config.cache_dir else None
        self._api_key = config.api_key.get_secret_value() if config.api_key else None
        mode = instructor.Mode.JSON_SCHEMA if config.structured_output == "json_schema" else instructor.Mode.JSON
        self._client = instructor.from_litellm(litellm.completion, mode=mode)  # type: ignore[reportUnknownMemberType]
        self._async_client = instructor.from_litellm(litellm.acompletion, mode=mode)  # type: ignore[reportUnknownMemberType]
        self._usage_lock = threading.Lock()
        self._usage = TokenUsage()

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

    def _call_kwargs(self, seed: int | None, max_tokens: int | None = None) -> dict[str, object]:
        """Provider-agnostic sampling kwargs. Unsupported params are dropped by LiteLLM."""
        kwargs: dict[str, object] = {
            "model": self.model,
            "max_tokens": max_tokens or self.max_tokens,
            "timeout": self.timeout_sec,
            "drop_params": True,
        }
        if not _accepts(self.model, "max_tokens"):
            kwargs["max_completion_tokens"] = kwargs.pop("max_tokens")
        if _accepts(self.model, "temperature"):
            kwargs["temperature"] = self.temperature
        # Claude models may think before answering (adaptive thinking), which can use up a small
        # max_tokens budget before any JSON is written. Shopper decisions are short: answer directly.
        if self.model.startswith("anthropic/") and _accepts(self.model, "thinking"):
            kwargs["thinking"] = _THINKING_OFF.get(self.model, {"type": "disabled"})
        # Hybrid Qwen models on Model Studio think by default (billed reasoning tokens, slower);
        # the OpenAI-compatible endpoint takes the switch as a top-level body field.
        if self.model.startswith("openai/qwen") and "aliyuncs.com" in (self.api_base or ""):
            kwargs["extra_body"] = {"enable_thinking": False}
        # OpenAI reasoning models (GPT-6 Luna) reason by default, and the reasoning tokens count
        # against max_completion_tokens: a 160-token glance budget was used up before any JSON, so
        # most glances failed. A model that refuses the switch is remembered and asked without it.
        if self._openai_hosted() and _accepts(self.model, "reasoning_effort"):
            kwargs["extra_body"] = {"reasoning_effort": "none"}
        if self.api_base:
            kwargs["api_base"] = self.api_base
            # Local OpenAI-compatible servers (llama.cpp, vLLM) usually need no key, but the OpenAI
            # SDK refuses to send a request without one.
            if self.model.startswith("openai/") and not os.environ.get("OPENAI_API_KEY"):
                kwargs["api_key"] = os.environ.get("PARASTORE_LOCAL_API_KEY", "not-needed")
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

    def _accumulate_usage(self, raw_response: object, rid: str) -> None:
        usage = getattr(raw_response, "usage", None)
        with self._usage_lock:
            self._usage.requests += 1
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
    # Content-addressed: identical (model, sampling params, seed, schema, prompts) → identical
    # response. Makes reruns free, keeps paired experiments exact, and survives crashes.

    def _cache_path(
        self, response_model: type[BaseModel], messages: object, seed: int | None, max_tokens: int | None = None,
    ) -> Path | None:
        if self.cache_dir is None:
            return None
        extra: dict[str, str] = {"reasoning": "none"} if self._openai_hosted() else {}
        key_src = json.dumps(
            {
                **extra,
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
        if path is None or not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            result = response_model.model_validate(data["result"])
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
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(f".{os.getpid()}.{threading.get_ident()}.tmp")
        tmp.write_text(json.dumps({"result": result.model_dump(mode="json")}, ensure_ascii=False), encoding="utf-8")
        replace_file(tmp, path)

    def _create(self, response_model: type[BaseModel], msgs: object, max_retries: int,
                seed: int | None, max_tokens: int | None = None) -> tuple[object, object]:
        for attempt in range(_ATTEMPTS):
            kwargs = self._call_kwargs(seed, max_tokens)
            try:
                return self._client.chat.completions.create_with_completion(  # type: ignore[reportUnknownMemberType]
                    response_model=response_model,
                    messages=msgs,  # type: ignore[reportArgumentType]
                    max_retries=max_retries,
                    **kwargs,  # type: ignore[reportArgumentType]  # LiteLLM kwargs are untyped
                )
            except Exception as e:
                if attempt < _ATTEMPTS - 1 and _should_retry_without(self.model, e, kwargs):
                    continue
                raise
        raise AssertionError("unreachable")

    async def _acreate(self, response_model: type[BaseModel], msgs: object, max_retries: int,
                       seed: int | None, max_tokens: int | None = None) -> tuple[object, object]:
        for attempt in range(_ATTEMPTS):
            kwargs = self._call_kwargs(seed, max_tokens)
            try:
                return await self._async_client.chat.completions.create_with_completion(  # type: ignore[reportUnknownMemberType]
                    response_model=response_model,
                    messages=msgs,  # type: ignore[reportArgumentType]
                    max_retries=max_retries,
                    **kwargs,  # type: ignore[reportArgumentType]  # LiteLLM kwargs are untyped
                )
            except Exception as e:
                if attempt < _ATTEMPTS - 1 and _should_retry_without(self.model, e, kwargs):
                    continue
                raise
        raise AssertionError("unreachable")

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
        cache_path = self._cache_path(response_model, msgs, seed)
        cached = self._cache_get(cache_path, response_model)
        if cached is not None:
            return cached
        model, raw = self._create(response_model, msgs, max_retries, seed)
        self._accumulate_usage(raw, rid)
        self._cache_put(cache_path, model)  # type: ignore[reportUnknownArgumentType]
        return model  # type: ignore[reportReturnType]

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
        cache_path = self._cache_path(response_model, msgs, seed, max_tokens)
        cached = self._cache_get(cache_path, response_model)
        if cached is not None:
            return cached
        model, raw = await self._acreate(response_model, msgs, max_retries, seed, max_tokens)
        self._accumulate_usage(raw, rid)
        self._cache_put(cache_path, model)  # type: ignore[reportUnknownArgumentType]
        return model  # type: ignore[reportReturnType]

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
        cache_path = self._cache_path(response_model, msgs, seed)
        cached = self._cache_get(cache_path, response_model)
        if cached is not None:
            return cached
        model, raw = self._create(response_model, msgs, max_retries, seed)
        self._accumulate_usage(raw, rid)
        self._cache_put(cache_path, model)  # type: ignore[reportUnknownArgumentType]
        return model  # type: ignore[reportReturnType]

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
        cache_path = self._cache_path(response_model, msgs, seed, max_tokens)
        cached = self._cache_get(cache_path, response_model)
        if cached is not None:
            return cached
        model, raw = await self._acreate(response_model, msgs, max_retries, seed, max_tokens)
        self._accumulate_usage(raw, rid)
        self._cache_put(cache_path, model)  # type: ignore[reportUnknownArgumentType]
        return model  # type: ignore[reportReturnType]

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
        for attempt in range(_ATTEMPTS):
            kwargs: dict[str, object] = {"messages": msgs, **self._call_kwargs(None)}
            if enable_search:
                kwargs["tools"] = [{"google_search": {}}]
            try:
                raw = await litellm.acompletion(**kwargs)  # type: ignore[reportUnknownMemberType]
                break
            except Exception as e:
                if attempt < _ATTEMPTS - 1 and _should_retry_without(self.model, e, kwargs):
                    continue
                raise
        self._accumulate_usage(raw, rid)
        choices: list[object] = list(getattr(raw, "choices", None) or [])
        if not choices:
            return ""
        first: object = choices[0]
        msg: object = getattr(first, "message", None)
        return str(getattr(msg, "content", "") or "")
