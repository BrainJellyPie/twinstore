"""Model providers: presets, locally stored API keys, model-reference resolution, connection tests.

Keys come from (in order) the settings file written by the UI, then the provider's usual
environment variable (OPENAI_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY, DASHSCOPE_API_KEY, …).
The settings file lives in `.data/settings/providers.json` (git-ignored, mode 600) and keys are
never returned by the API, logged, or written into run directories (`LLMConfig.api_key` is
excluded from serialization).
"""

import asyncio
import base64
import io
import logging
import os
import time
from pathlib import Path
from typing import cast

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
from store_emulator.engine.llm_client import LiteLLMClient
from store_emulator.engine.llm_router import EnsembleLLMClient, SimLLM

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
        default_api_base="http://127.0.0.1:8001/v1", needs_key=False, structured_output="json_schema", local=True,
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
        default_api_base="http://127.0.0.1:8081/v1", needs_key=False, structured_output="json_schema", local=True,
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
    api_base: str | None
    default_model: str | None
    ready: bool


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


def update_provider(kind: ProviderKind, update: ProviderUpdate) -> ProviderStatus:
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


def _key_for(kind: ProviderKind, settings: dict[ProviderKind, ProviderSettings]) -> tuple[str | None, str]:
    s = settings.get(kind)
    if s and s.api_key and s.api_key.get_secret_value():
        return s.api_key.get_secret_value(), "settings"
    env = PRESETS[kind].api_key_env
    if env and os.environ.get(env):
        return os.environ[env], "env"
    return None, "none"


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
    return ProviderStatus(
        preset=preset, enabled=enabled, has_key=key is not None, key_source=source,
        key_hint=f"…{key[-4:]}" if key and len(key) >= 8 else "",
        api_base=api_base, default_model=s.default_model,
        ready=enabled and (key is not None or not preset.needs_key) and (api_base is not None or not preset.local),
    )


def cloud_providers_with_key(settings: dict[ProviderKind, ProviderSettings] | None = None) -> list[str]:
    """Labels of the cloud providers that have a key (settings or environment)."""
    settings = settings if settings is not None else load_settings()
    return [preset.label for kind, preset in PRESETS.items()
            if preset.needs_key and not preset.local and _key_for(kind, settings)[0] is not None]


def use_local_server(api_base: str) -> ProviderStatus:
    """Point the llama.cpp provider at a server on this computer and turn it on (the local model)."""
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
    for status in list_providers():
        if not status.ready:
            continue
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
        return base.model_copy(update={"model": ref})
    settings = settings if settings is not None else load_settings()
    preset = PRESETS[parsed.provider]
    s = settings.get(parsed.provider, ProviderSettings(kind=parsed.provider))
    key, _ = _key_for(parsed.provider, settings)
    if preset.needs_key and key is None:
        raise ValueError(
            f"no API key for {preset.label}: add it in Settings → Model providers or set {preset.api_key_env}",
        )
    model_id = parsed.model
    if parsed.provider == ProviderKind.LLAMACPP and model_id == "local":
        model_id = "local-model"
    return base.model_copy(update={
        "model": f"{preset.litellm_prefix}/{model_id}",
        "api_base": _api_base(preset, s),
        "structured_output": preset.structured_output,
        "api_key": SecretStr(key) if key else None,
    })


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


def ensure_resolvable(config: SimulationConfig) -> None:
    """Raise ValueError (with a user-facing message) when a run's model references cannot be used."""
    if config.engine_type == EngineType.RULE_BASED:
        return
    settings = load_settings()
    refs = [m.model for m in config.ensemble.members] if config.ensemble is not None else [config.llm_for(config.engine_type).model]
    for ref in refs:
        resolved = resolve_model(ref, settings=settings)
        if "127.0.0.1" in (resolved.api_base or "") or ref.startswith("llamacpp:"):
            _ensure_local_ready()


def _ensure_local_ready() -> None:
    """A run on the local model while TwinStore is still fetching or starting it would only fail."""
    from .local_vlm import manager  # late import: local_vlm imports this module

    status = manager().status()
    if status.state in ("preparing", "downloading", "starting"):
        done = f" ({status.progress:.0%})" if status.progress is not None else ""
        raise ValueError(f"The local vision model is not ready yet: {status.message}{done}. "
                         "Try again in a moment, or add an API key in Settings → Model providers.")


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
    except Exception as e:  # noqa: BLE001 — report any provider error to the user verbatim
        return ConnectionTest(ok=False, model=ref, error=f"{type(e).__name__}: {e}"[:500], vision=vision,
                              latency_ms=int((time.perf_counter() - started) * 1000))
    return ConnectionTest(ok=ok, model=ref, reply=reply, vision=vision,
                          latency_ms=int((time.perf_counter() - started) * 1000))
