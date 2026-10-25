"""Model providers: presets, locally stored API keys, model-reference resolution, connection tests.

Keys come from (in order) the settings file written by the UI, then the provider's usual
environment variable (OPENAI_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY, DASHSCOPE_API_KEY, …).
The settings file lives in `.data/settings/providers.json` (git-ignored, mode 600) and keys are
never returned by the API, logged, or written into run directories (`LLMConfig.api_key` is
excluded from serialization).
"""

import asyncio
import base64
import hashlib
import io
import logging
import os
import threading
import time
import urllib.error
import urllib.request
import weakref
from collections.abc import Callable
from pathlib import Path
from typing import cast
from urllib.parse import urlsplit

from PIL import Image, ImageDraw
from pydantic import BaseModel, Field, SecretStr

from store_emulator.domain.config import EngineType, LLMConfig, SimulationConfig
from store_emulator.domain.providers import (
    EnsembleConfig,
    ModelRef,
    ModelSuggestion,
    ProviderKind,
    ProviderPreset,
)
from store_emulator.engine.llm_client import LiteLLMClient, is_auth_error
from store_emulator.engine.llm_router import EnsembleLLMClient, SimLLM

from .errors import model_failure
from .estimates import is_local_base
from .storage.io import DATA_DIR, read_json, write_json

logger = logging.getLogger(__name__)

PRESETS: dict[ProviderKind, ProviderPreset] = {
    ProviderKind.OPENAI: ProviderPreset(
        kind=ProviderKind.OPENAI, label="OpenAI", litellm_prefix="openai", api_key_env="OPENAI_API_KEY",
        structured_output="json_schema", docs_url="https://platform.openai.com/docs/models",
        models=[
            ModelSuggestion(id="gpt-6-luna", label="GPT-6 Luna", vision=True, note="fast, low cost"),
            ModelSuggestion(id="gpt-6-sol", label="GPT-6 Sol", vision=True),
            ModelSuggestion(id="gpt-5.6-luna", label="GPT-5.6 Luna", vision=True),
        ],
    ),
    ProviderKind.ANTHROPIC: ProviderPreset(
        kind=ProviderKind.ANTHROPIC, label="Anthropic (Claude)", litellm_prefix="anthropic",
        api_key_env="ANTHROPIC_API_KEY", docs_url="https://docs.claude.com/en/docs/about-claude/models",
        models=[
            ModelSuggestion(id="claude-haiku-5-5", label="Claude Haiku 5.5", vision=True, note="fast, low cost"),
            ModelSuggestion(id="claude-sonnet-5-5", label="Claude Sonnet 5.5", vision=True),
            ModelSuggestion(id="claude-opus-5-5", label="Claude Opus 5.5", vision=True),
        ],
    ),
    ProviderKind.GEMINI: ProviderPreset(
        kind=ProviderKind.GEMINI, label="Google Gemini", litellm_prefix="gemini", api_key_env="GEMINI_API_KEY",
        docs_url="https://ai.google.dev/gemini-api/docs/models",
        models=[
            ModelSuggestion(id="gemini-3.8-flash", label="Gemini 3.8 Flash", vision=True, note="fast"),
            ModelSuggestion(id="gemini-3.5-flash-lite", label="Gemini 3.5 Flash-Lite", vision=True, note="lowest cost"),
            ModelSuggestion(id="gemini-4-argon", label="Gemini 4 Argon", vision=True),
            ModelSuggestion(id="gemini-3.1-pro-preview", label="Gemini 3.1 Pro (preview)", vision=True),
        ],
    ),
    ProviderKind.QWEN: ProviderPreset(
        kind=ProviderKind.QWEN, label="Alibaba Cloud Qwen (Model Studio)", litellm_prefix="openai",
        default_api_base="https://dashscope-intl.aliyuncs.com/compatible-mode/v1", api_key_env="DASHSCOPE_API_KEY",
        # Other regions: Settings → API base, or DASHSCOPE_API_BASE (US: dashscope-us…; Frankfurt has only
        # workspace endpoints, https://<workspace>.eu-central-1.maas.aliyuncs.com/compatible-mode/v1).
        api_base_env="DASHSCOPE_API_BASE",
        docs_url="https://www.alibabacloud.com/help/en/model-studio/compatibility-of-openai-with-dashscope",
        models=[
            ModelSuggestion(id="qwen3.7-plus", label="Qwen3.7-Plus", vision=True, note="text + image"),
            ModelSuggestion(id="qwen3-vl-plus", label="Qwen3-VL-Plus", vision=True),
            ModelSuggestion(id="qwen3.8-flash", label="Qwen3.8-Flash", note="fast, low cost"),
            ModelSuggestion(id="qwen-flash", label="Qwen Flash", note="low cost"),
        ],
    ),
    ProviderKind.VLLM: ProviderPreset(
        kind=ProviderKind.VLLM, label="vLLM (self-hosted)", litellm_prefix="openai",
        default_api_base="http://127.0.0.1:8001/v1", api_key_env="PARASTORE_LOCAL_API_KEY",
        needs_key=False, structured_output="json_schema", local=True,
        docs_url="https://docs.vllm.ai/en/latest/serving/openai_compatible_server.html",
        models=[
            ModelSuggestion(id="Qwen/Qwen3.5-9B", label="Qwen3.5-9B (served name)", vision=True),
            ModelSuggestion(id="Qwen/Qwen3.5-2B", label="Qwen3.5-2B (served name)", vision=True),
        ],
    ),
    ProviderKind.OLLAMA: ProviderPreset(
        kind=ProviderKind.OLLAMA, label="Ollama", litellm_prefix="ollama_chat",
        default_api_base="http://127.0.0.1:11434", needs_key=False, local=True,
        models=[ModelSuggestion(id="qwen3.5:2b", label="qwen3.5:2b", vision=True)],
    ),
    ProviderKind.LLAMACPP: ProviderPreset(
        kind=ProviderKind.LLAMACPP, label="llama.cpp server", litellm_prefix="openai",
        default_api_base="http://127.0.0.1:8081/v1", api_key_env="PARASTORE_LOCAL_API_KEY",
        needs_key=False, structured_output="json_schema", local=True,
        models=[ModelSuggestion(id="local", label="Model loaded in llama-server", vision=True)],
    ),
    ProviderKind.OPENROUTER: ProviderPreset(
        kind=ProviderKind.OPENROUTER, label="OpenRouter", litellm_prefix="openrouter",
        api_key_env="OPENROUTER_API_KEY", models=[],
    ),
    ProviderKind.CUSTOM: ProviderPreset(
        kind=ProviderKind.CUSTOM, label="Other OpenAI-compatible", litellm_prefix="openai",
        api_key_env="CUSTOM_LLM_API_KEY", needs_key=False, structured_output="json_schema", local=True, models=[],
    ),
}


class ProviderSettings(BaseModel):
    kind: ProviderKind
    enabled: bool = True
    api_key: SecretStr | None = None
    api_base: str | None = None
    default_model: str | None = None


class ProviderUpdate(BaseModel):
    enabled: bool | None = None
    api_key: str | None = Field(default=None, description="New key; empty string clears the stored key")
    api_base: str | None = None
    default_model: str | None = None


class ProviderStatus(BaseModel):
    """What the API returns: never the key itself."""
    preset: ProviderPreset
    enabled: bool
    has_key: bool
    key_source: str                 # "settings" | "env" | "none" | "not needed"
    key_hint: str                   # last 4 characters, or ""
    key_rejected: bool = False      # the provider turned this key down during this session
    api_base: str | None
    default_model: str | None
    ready: bool
    # A server on this computer (llama.cpp, Ollama, …) at api_base answers right now; None: not checked (not a local
    # provider, turned off, or on another computer). An address an earlier session left behind is no running server.
    answers: bool | None = None


class ConnectionTest(BaseModel):
    ok: bool
    model: str
    latency_ms: int = 0
    reply: str = ""
    error: str = ""
    vision: bool = False


def _settings_path() -> Path:
    return Path(os.environ.get("PARASTORE_SETTINGS_DIR", str(Path(DATA_DIR) / "settings"))) / "providers.json"


def load_settings() -> dict[ProviderKind, ProviderSettings]:
    path = _settings_path()
    out: dict[ProviderKind, ProviderSettings] = {}
    if path.exists():
        try:
            raw = cast(dict[str, object], read_json(path))
            for kind, value in raw.items():
                if kind in {k.value for k in ProviderKind} and isinstance(value, dict):
                    out[ProviderKind(kind)] = ProviderSettings.model_validate({**cast(dict[str, object], value), "kind": kind})
        except (OSError, ValueError) as e:
            logger.warning(f"[providers] ignoring unreadable settings file: {e}")
    return out


def _save_settings(settings: dict[ProviderKind, ProviderSettings]) -> None:
    path = _settings_path()
    data = {
        kind.value: {
            "enabled": s.enabled,
            "api_key": s.api_key.get_secret_value() if s.api_key else None,
            "api_base": s.api_base,
            "default_model": s.default_model,
        }
        for kind, s in settings.items()
    }
    write_json(path, data)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


# One read-change-write of the settings file at a time: a key saved in Settings while the local model became ready
# (which points the llama.cpp provider at it) could otherwise lose one of the two changes.
_SETTINGS_LOCK = threading.Lock()


def update_provider(kind: ProviderKind, update: ProviderUpdate) -> ProviderStatus:
    with _SETTINGS_LOCK:
        return _update_provider(kind, update)


def _update_provider(kind: ProviderKind, update: ProviderUpdate) -> ProviderStatus:
    settings = load_settings()
    current = settings.get(kind, ProviderSettings(kind=kind))
    changes: dict[str, object] = {}
    if update.enabled is not None:
        changes["enabled"] = update.enabled
    if update.api_key is not None:
        changes["api_key"] = SecretStr(update.api_key.strip()) if update.api_key.strip() else None
    if update.api_base is not None:
        changes["api_base"] = update.api_base.strip() or None
    if update.default_model is not None:
        changes["default_model"] = update.default_model.strip() or None
    settings[kind] = current.model_copy(update=changes)
    _save_settings(settings)
    return provider_status(kind, settings)


# Other environment variables LiteLLM reads for a provider's key, after the preset's own.
_ENV_ALIASES: dict[ProviderKind, tuple[str, ...]] = {ProviderKind.GEMINI: ("GOOGLE_API_KEY",)}


def _key_for(kind: ProviderKind, settings: dict[ProviderKind, ProviderSettings]) -> tuple[str | None, str]:
    s = settings.get(kind)
    if s and s.api_key and s.api_key.get_secret_value():
        return s.api_key.get_secret_value(), "settings"
    for env in (PRESETS[kind].api_key_env, *_ENV_ALIASES.get(kind, ())):
        if env and os.environ.get(env, "").strip():
            return os.environ[env].strip(), "env"
    return None, "none"


# Keys a provider turned down during this session (not valid, revoked), by fingerprint. They count as no key, so
# assistive features move on to another provider or the local model; a new key (another fingerprint) is tried again.
_REJECTED_KEYS: dict[ProviderKind, str] = {}
_REJECTED_LOCK = threading.Lock()


def _fingerprint(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def reject_key(kind: ProviderKind, key: str) -> None:
    with _REJECTED_LOCK:
        new = _REJECTED_KEYS.get(kind) != _fingerprint(key)
        _REJECTED_KEYS[kind] = _fingerprint(key)
    if new:
        logger.warning(f"[providers] {PRESETS[kind].label} turned the API key …{key[-4:]} down; "
                       "it is set aside until it is replaced")


def accept_key(kind: ProviderKind, key: str) -> None:
    """The provider answered with this key (a passing connection test): it is usable again."""
    with _REJECTED_LOCK:
        if _REJECTED_KEYS.get(kind) == _fingerprint(key):
            del _REJECTED_KEYS[kind]


def _rejected(kind: ProviderKind, key: str | None) -> bool:
    return key is not None and _REJECTED_KEYS.get(kind) == _fingerprint(key)


def _usable_key(kind: ProviderKind, settings: dict[ProviderKind, ProviderSettings]) -> str | None:
    key, _ = _key_for(kind, settings)
    return None if _rejected(kind, key) else key


def key_rejected(kind: ProviderKind, settings: dict[ProviderKind, ProviderSettings] | None = None) -> bool:
    settings = settings if settings is not None else load_settings()
    return _rejected(kind, _key_for(kind, settings)[0])


def _api_base(preset: ProviderPreset, s: ProviderSettings) -> str | None:
    """Settings first, then the preset's environment override, then the preset default."""
    env = os.environ.get(preset.api_base_env) if preset.api_base_env else None
    return s.api_base or env or preset.default_api_base


def provider_status(kind: ProviderKind, settings: dict[ProviderKind, ProviderSettings] | None = None) -> ProviderStatus:
    settings = settings if settings is not None else load_settings()
    preset = PRESETS[kind]
    stored = settings.get(kind)
    s = stored or ProviderSettings(kind=kind)
    key, source = _key_for(kind, settings)
    if not preset.needs_key and key is None:
        source = "not needed"
    # Local servers are off until the user turns them on: a default endpoint is no proof that a
    # server is running there, and offering it in model pickers would only produce failed runs.
    enabled = s.enabled if stored is not None else not preset.local
    api_base = _api_base(preset, s)
    rejected = _rejected(kind, key)
    return ProviderStatus(
        preset=preset, enabled=enabled, has_key=key is not None, key_source=source,
        key_hint=f"…{key[-4:]}" if key and len(key) >= 8 else "", key_rejected=rejected,
        api_base=api_base, default_model=s.default_model,
        ready=enabled and ((key is not None and not rejected) or not preset.needs_key)
        and (api_base is not None or not preset.local),
    )


def cloud_providers_with_key(settings: dict[ProviderKind, ProviderSettings] | None = None) -> list[str]:
    """Labels of the cloud providers that have a key (settings or environment) the provider has not turned down."""
    settings = settings if settings is not None else load_settings()
    return [preset.label for kind, preset in PRESETS.items()
            if preset.needs_key and not preset.local and _usable_key(kind, settings) is not None]


def use_local_server(api_base: str) -> ProviderStatus:
    """Point the llama.cpp provider at a server on this computer and turn it on (the local model)."""
    with _SETTINGS_LOCK:
        settings = load_settings()
        current = settings.get(ProviderKind.LLAMACPP, ProviderSettings(kind=ProviderKind.LLAMACPP))
        settings[ProviderKind.LLAMACPP] = current.model_copy(update={
            "enabled": True, "api_base": api_base, "default_model": current.default_model or "local"})
        _save_settings(settings)
        return provider_status(ProviderKind.LLAMACPP, settings)


def list_providers() -> list[ProviderStatus]:
    settings = load_settings()
    return [provider_status(kind, settings) for kind in PRESETS]


def available_models() -> list[dict[str, object]]:
    """Model references usable right now (provider ready), for model pickers."""
    out: list[dict[str, object]] = []
    settings = load_settings()
    for status in list_providers():
        if not status.ready:
            continue
        if status.preset.kind == ProviderKind.LLAMACPP and not _local_text_ready(settings):
            continue   # its settings outlive the server (a stopped local model, a port from last time)
        ids = [m.id for m in status.preset.models]
        if status.default_model and status.default_model not in ids:
            ids.insert(0, status.default_model)
        for model_id in ids:
            meta = next((m for m in status.preset.models if m.id == model_id), None)
            out.append({
                "ref": f"{status.preset.kind.value}:{model_id}",
                "provider": status.preset.label,
                "label": meta.label if meta else model_id,
                "vision": meta.vision if meta else True,
                "local": status.preset.local,
            })
    return out


def resolve_model(
    ref: str, *, base: LLMConfig | None = None, settings: dict[ProviderKind, ProviderSettings] | None = None,
) -> LLMConfig:
    """Model reference → LLMConfig. Plain LiteLLM strings ("gemini/…") pass through unchanged.

    Sampling settings (temperature, max_tokens, seed, cache, timeout) are kept from `base`.
    """
    base = base or LLMConfig()
    parsed = ModelRef.parse(ref)
    if parsed is None:
        resolved = _on_local_server(base.model_copy(update={"model": ref}))
        resolved = resolved.model_copy(update={"cache_namespace": _local_cache_namespace(resolved.api_base)})
        kind = _PLAIN_PREFIX.get(ref.partition("/")[0])
        if kind is None or base.api_base is not None or base.api_key is not None:
            return resolved
        # The key the app shows for this provider, also when it was entered in Settings rather than the environment
        # (LiteLLM reads only the environment, and for Gemini prefers GOOGLE_API_KEY to GEMINI_API_KEY).
        key, _ = _key_for(kind, settings if settings is not None else load_settings())
        return resolved.model_copy(update={"api_key": SecretStr(key)}) if key else resolved
    settings = settings if settings is not None else load_settings()
    preset = PRESETS[parsed.provider]
    s = settings.get(parsed.provider, ProviderSettings(kind=parsed.provider))
    key, _ = _key_for(parsed.provider, settings)
    if preset.needs_key and key is None:
        raise ValueError(
            f"no API key for {preset.label}: add it in Settings → Model providers or set {preset.api_key_env}",
        )
    model_id = parsed.model
    parallel: int | None = None
    if parsed.provider == ProviderKind.LLAMACPP and model_id == "local":
        model_id = "local-model"
        parallel = _local_slots(_api_base(preset, s))
    api_base = _api_base(preset, s)
    if not key and preset.local and preset.litellm_prefix == "openai":
        # The SDK needs a key even for no-auth servers. An explicit placeholder
        # prevents it from borrowing another provider's environment credential.
        key = "not-needed"
    return base.model_copy(update={
        "model": f"{preset.litellm_prefix}/{model_id}",
        "api_base": api_base,
        "structured_output": preset.structured_output,
        "api_key": SecretStr(key) if key else None,
        "max_parallel": parallel or base.max_parallel,
        "cache_namespace": _local_cache_namespace(api_base),
    })


def _local_cache_namespace(api_base: str | None) -> str:
    """Identify the loaded artifacts, not a recommendation for an external or stopped server."""
    if not api_base:
        return ""
    from .local_vlm import manager

    status = manager().status()
    if (status.state != "ready" or not status.managed or status.plan is None
            or not status.api_base or status.api_base.rstrip("/") != api_base.rstrip("/")):
        return ""
    model = status.plan.model
    artifacts = "\0".join((model.repo, model.file, model.mmproj))
    return "managed-local:" + hashlib.sha256(artifacts.encode()).hexdigest()


def _on_local_server(config: LLMConfig) -> LLMConfig:
    """A model at the local model's usual address (the default vision model, `openai/local-vlm` at port 8081) goes
    where TwinStore's own server runs now — another port when 8081 was taken — with its request limit."""
    usual = (PRESETS[ProviderKind.LLAMACPP].default_api_base or "").rstrip("/")
    if not config.api_base or config.api_base.rstrip("/") != usual:
        return config
    from .local_vlm import manager  # late import: local_vlm imports this module

    status = manager().status()
    if status.state != "ready" or not status.api_base:
        return config
    return config.model_copy(update={"api_base": status.api_base,
                                     "max_parallel": config.max_parallel or status.slots or None})


def _local_slots(api_base: str | None) -> int | None:
    """How many requests the local model server takes at once, when `api_base` is the one TwinStore uses (started by
    it, or found already running on this computer)."""
    from .local_vlm import manager  # late import: local_vlm imports this module

    status = manager().status()
    if status.state == "ready" and status.slots > 0 and api_base and status.api_base == api_base:
        return status.slots
    return None


# Cloud providers tried, in order, when the app's text model has no key (assistive features only).
_FALLBACK_ORDER = (ProviderKind.ANTHROPIC, ProviderKind.OPENAI, ProviderKind.GEMINI, ProviderKind.QWEN, ProviderKind.OPENROUTER)
_PLAIN_PREFIX = {"gemini": ProviderKind.GEMINI, "anthropic": ProviderKind.ANTHROPIC, "openai": ProviderKind.OPENAI,
                 "openrouter": ProviderKind.OPENROUTER}


def text_model_fallback(model: str, settings: dict[ProviderKind, ProviderSettings] | None = None) -> str | None:
    """A model reference to use instead of `model` when its provider has no API key: the first fast model of the
    first cloud provider that has one; with no cloud key at all, the local model TwinStore runs on this computer
    (it reads text as well as shelves) once it is up. None when `model` can be used as it is, or nothing else can."""
    settings = settings if settings is not None else load_settings()
    kind = missing_key(model, settings)
    if kind is None:
        return None
    return _next_text_model(kind, settings)


def _next_text_model(kind: ProviderKind, settings: dict[ProviderKind, ProviderSettings]) -> str | None:
    for other in _FALLBACK_ORDER:
        preset = PRESETS[other]
        if other != kind and preset.models and provider_status(other, settings).ready:
            fast = next((m for m in preset.models if "fast" in m.note), preset.models[0])
            return f"{other.value}:{fast.id}"
    if _local_text_ready(settings):
        return f"{ProviderKind.LLAMACPP.value}:local"
    return None


def _local_text_ready(settings: dict[ProviderKind, ProviderSettings]) -> bool:
    """The llama.cpp server is set up and answering: TwinStore's own local model once it is ready, or a server the
    user turned on in Settings. The settings outlive the app, so with TwinStore's own model not running, the address
    they hold (often where it ran last time) must answer now."""
    status = provider_status(ProviderKind.LLAMACPP, settings)
    if not status.ready or status.api_base is None or not _valid_api_base(status.api_base):
        return False
    # late import: local_vlm imports this module
    from .local_vlm import manager, server_answers

    local = manager().status()
    try:
        requested = urlsplit(status.api_base)
        managed = urlsplit(local.api_base or PRESETS[ProviderKind.LLAMACPP].default_api_base or "")
        same_endpoint = (
            requested.scheme == managed.scheme and requested.port == managed.port
            and requested.path.rstrip("/") == managed.path.rstrip("/") and requested.query == managed.query
            and requested.hostname == managed.hostname
        )
    except ValueError:
        return False
    if same_endpoint:
        if local.state == "ready" and local.api_base is not None:
            return True
        if local.state not in ("off", "disabled", "ready"):
            return False
    return server_answers(status.api_base)


def assistive_model(requested: str, config: LLMConfig) -> str:
    """The model an assistive feature (interviews, commentary, set-up helpers) uses: the one asked for, else the app's
    text model, else, when that has no API key, a fast model of a provider that has one. Simulation runs and studies
    keep their configured model and never fall back."""
    if requested.strip():
        return requested.strip()
    # Plain LiteLLM references retain the endpoint and key supplied in the app configuration.
    if ModelRef.parse(config.model) is None and (
        config.api_base or (config.api_key and config.api_key.get_secret_value().strip())
    ):
        return config.model
    alternative = text_model_fallback(config.model)
    if alternative is not None:
        logger.info(f"[providers] {config.model} has no API key; assistive features use {alternative}")
        return alternative
    return config.model


def _same_local_endpoint(first: str, second: str) -> bool:
    """Match a concrete API endpoint; loopback host aliases can serve different models."""
    try:
        a, b = urlsplit(first), urlsplit(second)
        return a.hostname is not None and (
            a.scheme, a.hostname, a.port, a.path.rstrip("/"), a.query, a.username, a.password
        ) == (
            b.scheme, b.hostname, b.port, b.path.rstrip("/"), b.query, b.username, b.password
        )
    except ValueError:
        return False


def _valid_api_base(api_base: str) -> bool:
    try:
        endpoint = urlsplit(api_base)
        return (endpoint.scheme in {"http", "https"} and bool(endpoint.hostname)
                and (endpoint.port is None or endpoint.port > 0))
    except ValueError:
        return False


def _targets_own_local_server(vision: LLMConfig) -> bool:
    """Whether the app's vision model is the local model TwinStore runs on this computer (its address)."""
    if not vision.api_base or not _valid_api_base(vision.api_base):
        return False
    endpoint = urlsplit(vision.api_base)
    loopback = {"127.0.0.1", "localhost", "::1"}
    if endpoint.hostname not in loopback:
        return False
    from .local_vlm import manager  # late import: local_vlm imports this module

    managed = urlsplit(manager().status().api_base or PRESETS[ProviderKind.LLAMACPP].default_api_base or "")
    return managed.hostname in loopback and _same_local_endpoint(vision.api_base, managed.geturl())


def _cloud_vision_model(settings: dict[ProviderKind, ProviderSettings]) -> str:
    for kind in _FALLBACK_ORDER:
        seeing = [m for m in PRESETS[kind].models if m.vision]
        if seeing and provider_status(kind, settings).ready:
            fast = next((m for m in seeing if "fast" in m.note), seeing[0])
            return f"{kind.value}:{fast.id}"
    return ""


def run_vision_model(vision: LLMConfig) -> str:
    """The vision model a run that names none uses: with the app's vision model on the local model of this computer
    (the no-key fallback) and a cloud provider connected, that provider's fast vision model — a key added in Settings
    is what vision shoppers should use, faster and better than the small local model. "" = the app's vision model."""
    if not _targets_own_local_server(vision):
        return ""
    return _cloud_vision_model(load_settings())


def assistive_vision_model(requested: str, vision: LLMConfig) -> str:
    """The vision model an assistive feature (reading a pack) uses: the one asked for; else the app's vision model,
    unless it targets the app's local server and it is not running while a cloud provider with a key is set up, in which case
    that provider's fast vision model. "" = the app's vision model."""
    if requested.strip():
        return requested.strip()
    if not vision.api_base or not _valid_api_base(vision.api_base):
        return ""
    endpoint = urlsplit(vision.api_base)
    loopback = {"127.0.0.1", "localhost", "::1"}
    if endpoint.hostname not in loopback:
        return ""
    from .local_vlm import manager  # late import: local_vlm imports this module

    status = manager().status()
    if status.state == "ready":
        return ""
    managed = urlsplit(status.api_base or PRESETS[ProviderKind.LLAMACPP].default_api_base or "")
    if managed.hostname not in loopback or not _same_local_endpoint(vision.api_base, managed.geturl()):
        return ""
    settings = load_settings()
    for kind in _FALLBACK_ORDER:
        preset = PRESETS[kind]
        seeing = [m for m in preset.models if m.vision]
        if seeing and provider_status(kind, settings).ready:
            fast = next((m for m in seeing if "fast" in m.note), seeing[0])
            return f"{kind.value}:{fast.id}"
    return ""


def build_client(
    config: LLMConfig, ensemble: EnsembleConfig | None = None, *, model_ref: str | None = None,
) -> SimLLM:
    """One client, or an ensemble client whose members share the base sampling settings."""
    if ensemble is None or not ensemble.members:
        return LiteLLMClient(resolve_model(model_ref or config.model, base=config))
    settings = load_settings()
    members: list[tuple[str, float, SimLLM]] = []
    for member in ensemble.members:
        member_config = resolve_model(member.model, base=config, settings=settings)
        members.append((member.name, member.weight, LiteLLMClient(member_config)))
    return EnsembleLLMClient(members, mode=ensemble.mode, seed=ensemble.seed)


# ── assistive features: move on when a key is turned down ───────────────────

# Local-model states worth waiting through, and those that will not come right by waiting.
_LOCAL_COMING = ("preparing", "downloading", "starting")


class _Fallback:
    """The reroute an assistive client gets (engine/llm_client.py). When the provider turns the key down, the key is set
    aside for this session and the call moves on: to a fast model of another provider with a key, else to the local
    model on this computer, started if the app was opened from its icon and waited for up to `wait` seconds (background
    jobs wait; a request a person is waiting on does not). `on_wait` hears what the local model is doing meanwhile."""

    def __init__(self, ref: str, base: LLMConfig, *, wait: float, on_wait: Callable[[str], None] | None) -> None:
        self.ref, self._base, self._wait, self._on_wait = ref, base, wait, on_wait
        self._lock = threading.Lock()
        try:
            self.config = resolve_model(ref, base=base)
        except ValueError:                         # a reference without any key: the first call moves on
            self.config = base.model_copy(update={"model": ref})

    def __call__(self, failed: str, error: BaseException) -> LLMConfig | None:
        with self._lock:
            if failed != self.config.model:        # another call already moved on
                return self.config
            kind = _provider_of(self.ref)
            if kind is None or not PRESETS[kind].needs_key:
                return None
            if self.config.api_key is not None:
                reject_key(kind, self.config.api_key.get_secret_value())
            return self.move_on(kind, error)

    def move_on(self, kind: ProviderKind, error: BaseException | None) -> LLMConfig:
        nxt = _next_text_model(kind, load_settings()) or self._local(kind, error)
        # Settings read afresh: waiting for the local model may have pointed it at another port.
        self.ref, self.config = nxt, resolve_model(nxt, base=self._base)
        return self.config

    def _local(self, kind: ProviderKind, error: BaseException | None) -> str:
        from .local_vlm import manager  # late import: local_vlm imports this module

        label = PRESETS[kind].label
        settings = load_settings()
        rejected = key_rejected(kind, settings)
        reason = _short_reason(error) if error is not None else "not valid or revoked"
        if rejected:
            problem, fix = f"{label} turned the API key down ({reason})", "replace the key in Settings → Model providers"
        elif not any(_usable_key(k, settings) for k, preset in PRESETS.items() if preset.needs_key):
            # Nobody picked a provider: naming the default model's would send them to that one for no reason.
            problem, fix = "No model API key is set", "add a key for any provider in Settings → Model providers"
        else:
            problem, fix = f"No API key for {label}", "add a key in Settings → Model providers"
        local = manager()
        # Off, or failed last time (a dropped download, a server that crashed): start it again, once per request —
        # "Try again" on a failed generation would otherwise repeat the old failure without trying. Only a model the
        # user set up: nothing is downloaded for them unasked.
        starting = (local.status().state in ("off", "error") and os.environ.get("TWINSTORE_LOCAL_VLM_AUTO") == "1"
                    and local.auto_start())
        deadline = time.monotonic() + self._wait
        restarted_seen = False
        while True:
            status = local.status()
            if status.state == "ready" and _local_text_ready(load_settings()):
                logger.warning(f"[providers] {problem}; assistive features use the local model")
                return f"{ProviderKind.LLAMACPP.value}:local"
            if status.state not in _LOCAL_COMING and not (starting and status.state == "off" and local.busy()):
                if starting and status.state == "error" and not restarted_seen:
                    restarted_seen = True     # the error may be the old one, before the restart got going
                    time.sleep(1.0)
                    continue
                if status.state == "disabled":
                    raise ValueError(f"{problem}, and the local model on this computer is turned off "
                                     f"(TWINSTORE_LOCAL_VLM). {fix[0].upper()}{fix[1:]}, or turn the local model on.")
                why = f" (the local model: {status.message})" if status.state == "error" and status.message else ""
                other = "" if problem.startswith("No model API key") else ", or add another provider's key"
                local_hint = (" You can also start the local model in Settings → Model providers (it downloads once)."
                              if status.state == "off" else "")
                raise ValueError(f"{problem}{why}. {fix[0].upper()}{fix[1:]}{other}.{local_hint}")
            done = f" ({status.progress:.0%})" if status.progress is not None else ""
            if time.monotonic() >= deadline:
                raise ValueError(f"{problem}. The local model on this computer is getting ready ({status.message}"
                                 f"{done}): try again once it is, or {fix}.")
            if self._on_wait is not None:
                self._on_wait(f"{problem}; waiting for the local model: {status.message}{done}")
            time.sleep(2.0)


def _short_reason(error: BaseException) -> str:
    text = str(error)
    for marker in ("API key not valid", "invalid x-api-key", "Incorrect API key", "invalid_api_key", "API_KEY_INVALID"):
        if marker.lower() in text.lower():
            return marker
    return "authentication failed"


_FALLBACKS: "weakref.WeakKeyDictionary[LiteLLMClient, _Fallback]" = weakref.WeakKeyDictionary()


def answered_by(llm: object, ref: str) -> str:
    """The model that answered an assistive client: `ref`, unless the client moved on (a key turned down)."""
    fallback = _FALLBACKS.get(llm) if isinstance(llm, LiteLLMClient) else None
    return fallback.ref if fallback is not None else ref


def assistive_client(
    requested: str, config: LLMConfig, *, wait: float = 0.0, on_wait: Callable[[str], None] | None = None,
) -> LiteLLMClient:
    """The client of an assistive feature (`assistive_model` picks its model), moving on to another model when the
    provider turns the key down. With no usable key anywhere it starts on the local model right away, waiting up to
    `wait` seconds for it (a background job; this call then blocks), or raises ValueError saying what to do — no
    request is sent without a key. A model on an endpoint of the app configuration is used as it is."""
    ref = assistive_model(requested, config)
    fallback = _Fallback(ref, config, wait=wait, on_wait=on_wait)
    own_endpoint = ref == config.model and (config.api_base is not None or config.api_key is not None)
    kind = None if own_endpoint else missing_key(ref)
    if kind is not None:
        fallback.move_on(kind, None)
    # One rejected key per cloud provider, then the local model. A generic client's
    # smaller reroute limit can stop before this application-owned chain reaches it.
    client = LiteLLMClient(fallback.config, reroute=fallback, max_reroutes=len(_FALLBACK_ORDER))
    _FALLBACKS[client] = fallback
    return client


# ── key check at start ──────────────────────────────────────────────────────

_KEY_CHECKS: dict[ProviderKind, tuple[str, Callable[[str], dict[str, str]]]] = {
    ProviderKind.OPENAI: ("https://api.openai.com/v1/models", lambda k: {"Authorization": f"Bearer {k}"}),
    ProviderKind.ANTHROPIC: ("https://api.anthropic.com/v1/models",
                             lambda k: {"x-api-key": k, "anthropic-version": "2023-06-01"}),
    ProviderKind.GEMINI: ("https://generativelanguage.googleapis.com/v1beta/models", lambda k: {"x-goog-api-key": k}),
    ProviderKind.OPENROUTER: ("https://openrouter.ai/api/v1/key", lambda k: {"Authorization": f"Bearer {k}"}),
}


def _key_turned_down(kind: ProviderKind, key: str, settings: dict[ProviderKind, ProviderSettings],
                     opener: Callable[[urllib.request.Request], object]) -> bool | None:
    """True when the provider refuses the key, False when it takes it, None when it cannot tell (offline, no check)."""
    if kind == ProviderKind.QWEN:
        base = _api_base(PRESETS[kind], settings.get(kind, ProviderSettings(kind=kind)))
        url, headers = (f"{base.rstrip('/')}/models", {"Authorization": f"Bearer {key}"}) if base else ("", {})
    elif kind in _KEY_CHECKS:
        url, make = _KEY_CHECKS[kind]
        headers = make(key)
    else:
        return None
    if not url:
        return None
    try:
        opener(urllib.request.Request(url, headers=headers))
        return False
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            return True
        if e.code == 400:
            try:
                body = e.read().decode("utf-8", "replace")
            except OSError:
                body = ""
            return "API_KEY_INVALID" in body or "api key not valid" in body.lower()
        return None
    except (OSError, ValueError):
        return None


def _open_quietly(req: urllib.request.Request) -> object:
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.status


def check_keys(opener: Callable[[urllib.request.Request], object] = _open_quietly) -> list[str]:
    """Ask each cloud provider with a key whether it takes it (a free model listing, no tokens), and set aside the keys
    it turns down. Returns the labels of the providers whose key was turned down."""
    settings = load_settings()
    turned_down: list[str] = []
    for kind, preset in PRESETS.items():
        if not preset.needs_key or preset.local:
            continue
        key, _ = _key_for(kind, settings)
        if key is None:
            continue
        verdict = _key_turned_down(kind, key, settings, opener)
        if verdict:
            reject_key(kind, key)
            turned_down.append(preset.label)
        elif verdict is False:
            accept_key(kind, key)
    return turned_down


def ensure_resolvable(config: SimulationConfig) -> None:
    """Raise ValueError (with a user-facing message) when a run's model references cannot be used."""
    if config.engine_type == EngineType.RULE_BASED:
        return
    settings = load_settings()
    base = config.llm_for(config.engine_type)
    refs = [m.model for m in config.ensemble.members] if config.ensemble is not None else [base.model]
    for ref in refs:
        if base.api_base is None and base.api_key is None:
            _ensure_plain_key(ref, settings)
        resolved = resolve_model(ref, base=base, settings=settings)
        if resolved.api_base:
            ensure_local_ready(resolved.api_base)


def _provider_of(ref: str) -> ProviderKind | None:
    parsed = ModelRef.parse(ref)
    return parsed.provider if parsed is not None else _PLAIN_PREFIX.get(ref.partition("/")[0])


def missing_key(ref: str, settings: dict[ProviderKind, ProviderSettings] | None = None) -> ProviderKind | None:
    """The cloud provider of `ref` when it needs an API key and has none, or only one it turned down (plain LiteLLM
    strings and references)."""
    settings = settings if settings is not None else load_settings()
    kind = _provider_of(ref)
    if kind is None or not PRESETS[kind].needs_key or _usable_key(kind, settings) is not None:
        return None
    return kind


def _ensure_plain_key(ref: str, settings: dict[ProviderKind, ProviderSettings]) -> None:
    """A model of a cloud provider without a usable key would fail on every shopper; say so before the run starts, and
    name a model that would work. (A reference without any key is refused by resolve_model.)"""
    kind = missing_key(ref, settings)
    if kind is None:
        return
    rejected = key_rejected(kind, settings)
    if not rejected and ModelRef.parse(ref) is not None:
        return
    alternative = text_model_fallback(ref, settings)
    hint = ("Pick the local model on this computer for this run (llamacpp:local)" if alternative == "llamacpp:local"
            else f"Pick another model for this run ({alternative} has a key)" if alternative
            else "Use rule-based shoppers, wait for the local model to be ready")
    problem = (f"{PRESETS[kind].label} turned the API key down (not valid or revoked) for {ref}" if rejected
               else f"No API key for {PRESETS[kind].label} ({ref})")
    fix = "replace the key" if rejected else "add a key"
    raise ValueError(f"{problem}. {hint}, or {fix} in Settings → Model providers.")


def local_model_answers(api_base: str) -> bool:
    """Whether a model at this address can be used now: any address not on this computer counts (the provider says),
    a server on this computer must answer."""
    from .local_vlm import server_answers  # late import: local_vlm imports this module

    if not _valid_api_base(api_base):
        return False
    if not is_local_base(api_base):
        return True
    return server_answers(api_base)


def ensure_local_ready(api_base: str) -> None:
    """A run on a server on this computer that is not up would only fail — and vision shoppers whose every call fails
    fall back to rule-based decisions, so the run would even look fine."""
    # late import: local_vlm imports this module
    from .local_vlm import manager, server_answers

    if not _valid_api_base(api_base):
        raise ValueError("The model server address is invalid. Use an HTTP or HTTPS address with a valid host and port "
                         "in Settings → Model providers.")
    if not is_local_base(api_base):
        return
    status = manager().status()
    if status.state in ("preparing", "downloading", "starting"):
        managed = urlsplit(status.api_base or PRESETS[ProviderKind.LLAMACPP].default_api_base or "")
        if _same_local_endpoint(api_base, managed.geturl()):
            done = f" ({status.progress:.0%})" if status.progress is not None else ""
            raise ValueError(f"The local vision model is not ready yet: {status.message}{done}. "
                             "Try again in a moment, or add an API key in Settings → Model providers.")
    if not server_answers(api_base):
        if status.state == "disabled":
            # "Start it in Settings" cannot help: Settings says it is turned off and offers no Start.
            raise ValueError(f"No model server answers at {api_base}, and the local model on this computer is turned "
                             "off (TWINSTORE_LOCAL_VLM). Add an API key in Settings → Model providers and pick that "
                             "model for this run, or use rule-based shoppers.")
        raise ValueError(f"No model server answers at {api_base}: the local model is not running. Start it in "
                         "Settings → Model providers, or pick a cloud model for this run.")


class _Pong(BaseModel):
    ok: bool
    word: str = Field(default="", max_length=20)


class _SeenShape(BaseModel):
    color: str = Field(max_length=20)


def _tiny_png() -> str:
    img = Image.new("RGB", (96, 96), (255, 255, 255))
    ImageDraw.Draw(img).ellipse((18, 18, 78, 78), fill=(220, 30, 30))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


async def test_connection(ref: str, *, vision: bool = False) -> ConnectionTest:
    """Small structured call (and optionally an image call) against a model reference."""
    try:
        config = resolve_model(ref, base=LLMConfig(temperature=0.0, max_tokens=120, timeout_sec=60))
    except ValueError as e:
        return ConnectionTest(ok=False, model=ref, error=str(e))
    client = LiteLLMClient(config)
    kind = _provider_of(ref)
    started = time.perf_counter()
    try:
        if vision:
            seen = await asyncio.wait_for(client.generate_structured_with_image_async(
                _SeenShape, "Answer in JSON.", "What color is the circle? One word.", _tiny_png()), 90)
            reply = seen.color
            ok = "red" in seen.color.lower()
        else:
            pong = await asyncio.wait_for(client.generate_structured_async(
                _Pong, "Answer in JSON.", 'Reply with ok=true and word="pong".'), 90)
            reply, ok = pong.word, pong.ok
    except Exception as e:  # noqa: BLE001 — any provider error is reported, in words a user can act on
        logger.info(f"[providers] test of {ref} failed: {type(e).__name__}: {e}"[:2000])
        if is_auth_error(e):
            if kind is not None and config.api_key is not None:
                reject_key(kind, config.api_key.get_secret_value())
            who = PRESETS[kind].label if kind is not None else "The provider"
            message = f"{who} turned this key down ({_short_reason(e)}). Check the key, save it and test again."
        else:
            message = model_failure(e, "The test failed")
        return ConnectionTest(ok=False, model=ref, error=message[:500], vision=vision,
                              latency_ms=int((time.perf_counter() - started) * 1000))
    if kind is not None and config.api_key is not None:
        accept_key(kind, config.api_key.get_secret_value())
    return ConnectionTest(ok=ok, model=ref, reply=reply, vision=vision,
                          latency_ms=int((time.perf_counter() - started) * 1000))
