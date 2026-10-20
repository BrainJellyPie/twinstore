import hashlib
import json
import logging
import os
import threading
from pathlib import Path

import instructor
import litellm
from pydantic import BaseModel

from store_emulator.domain.config import LLMConfig
from store_emulator.domain.types import TokenUsage

logger = logging.getLogger(__name__)

# Most providers accept 32-bit seeds; larger values are folded into this range.
_SEED_MOD = 2**31 - 1


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
        self._client = instructor.from_litellm(litellm.completion, mode=instructor.Mode.JSON)  # type: ignore[reportUnknownMemberType]
        self._async_client = instructor.from_litellm(litellm.acompletion, mode=instructor.Mode.JSON)  # type: ignore[reportUnknownMemberType]
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

    def _call_kwargs(self, seed: int | None) -> dict[str, object]:
        """Provider-agnostic sampling kwargs. Unsupported params are dropped by LiteLLM."""
        kwargs: dict[str, object] = {
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "timeout": self.timeout_sec,
            "drop_params": True,
        }
        if self.api_base:
            kwargs["api_base"] = self.api_base
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

    def _cache_path(self, response_model: type[BaseModel], messages: object, seed: int | None) -> Path | None:
        if self.cache_dir is None:
            return None
        key_src = json.dumps(
            {
                "model": self.model,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
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
        os.replace(tmp, path)

    def generate_structured[T: BaseModel](
        self,
        response_model: type[T],
        system_prompt: str,
        user_prompt: str,
        *,
        max_retries: int = 1,
        seed: int | None = None,
    ) -> T:
        msgs, rid = self._messages(system_prompt, user_prompt)
        cache_path = self._cache_path(response_model, msgs, seed)
        cached = self._cache_get(cache_path, response_model)
        if cached is not None:
            return cached
        model, raw = self._client.chat.completions.create_with_completion(  # type: ignore[reportUnknownMemberType]
            response_model=response_model,
            messages=msgs,  # type: ignore[reportArgumentType]
            max_retries=max_retries,
            **self._call_kwargs(seed),  # type: ignore[reportArgumentType]  # LiteLLM kwargs are untyped
        )
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
    ) -> T:
        msgs, rid = self._messages(system_prompt, user_prompt)
        cache_path = self._cache_path(response_model, msgs, seed)
        cached = self._cache_get(cache_path, response_model)
        if cached is not None:
            return cached
        model, raw = await self._async_client.chat.completions.create_with_completion(  # type: ignore[reportUnknownMemberType]
            response_model=response_model,
            messages=msgs,  # type: ignore[reportArgumentType]
            max_retries=max_retries,
            **self._call_kwargs(seed),  # type: ignore[reportArgumentType]  # LiteLLM kwargs are untyped
        )
        self._accumulate_usage(raw, rid)
        self._cache_put(cache_path, model)  # type: ignore[reportUnknownArgumentType]
        return model  # type: ignore[reportReturnType]

    def generate_structured_with_image[T: BaseModel](
        self,
        response_model: type[T],
        system_prompt: str,
        user_prompt: str,
        image_url: str,
    ) -> T:
        msgs, rid = self._messages_with_image(system_prompt, user_prompt, image_url)
        model, raw = self._client.chat.completions.create_with_completion(  # type: ignore[reportUnknownMemberType]
            response_model=response_model,
            messages=msgs,  # type: ignore[reportArgumentType]
            **self._call_kwargs(None),  # type: ignore[reportArgumentType]  # LiteLLM kwargs are untyped
        )
        self._accumulate_usage(raw, rid)
        return model  # type: ignore[reportReturnType]

    async def generate_structured_with_image_async[T: BaseModel](
        self,
        response_model: type[T],
        system_prompt: str,
        user_prompt: str,
        image_url: str,
    ) -> T:
        msgs, rid = self._messages_with_image(system_prompt, user_prompt, image_url)
        model, raw = await self._async_client.chat.completions.create_with_completion(  # type: ignore[reportUnknownMemberType]
            response_model=response_model,
            messages=msgs,  # type: ignore[reportArgumentType]
            **self._call_kwargs(None),  # type: ignore[reportArgumentType]  # LiteLLM kwargs are untyped
        )
        self._accumulate_usage(raw, rid)
        return model  # type: ignore[reportReturnType]

    async def generate_text_async(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        enable_search: bool = False,
    ) -> str:
        """Bypass Instructor — raw text completion. Use when the schema varies by
        category and we need ad-hoc JSON output.

        enable_search=True enables the Gemini Search Grounding tool
        (Phase 0 spike confirmed `tools=[{"google_search": {}}]` works).
        Non-Gemini models may ignore it or raise BadRequest — caller must branch.
        """
        msgs, rid = self._messages(system_prompt, user_prompt)
        kwargs: dict[str, object] = {"messages": msgs, **self._call_kwargs(None)}
        if enable_search:
            kwargs["tools"] = [{"google_search": {}}]
        raw = await litellm.acompletion(**kwargs)  # type: ignore[reportUnknownMemberType]
        self._accumulate_usage(raw, rid)
        choices: list[object] = list(getattr(raw, "choices", None) or [])
        if not choices:
            return ""
        first: object = choices[0]
        msg: object = getattr(first, "message", None)
        return str(getattr(msg, "content", "") or "")
