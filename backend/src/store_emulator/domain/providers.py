"""Model providers, model references and ensembles of synthetic consumers.

A *model reference* is "<provider>:<model id>", e.g. "openai:gpt-6-luna",
"anthropic:claude-haiku-5-5", "gemini:gemini-3.8-flash", "qwen:qwen3.7-plus",
"vllm:Qwen/Qwen3.5-9B-VL" or "llamacpp:local". The application layer resolves a
reference to an `LLMConfig` (LiteLLM model string, endpoint, key); keys never
appear in references, run configs or manifests.
"""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class ProviderKind(StrEnum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    QWEN = "qwen"            # Alibaba Cloud Model Studio (DashScope), OpenAI-compatible mode
    VLLM = "vllm"            # self-hosted vLLM, OpenAI-compatible
    OLLAMA = "ollama"
    LLAMACPP = "llamacpp"    # llama.cpp llama-server, OpenAI-compatible
    OPENROUTER = "openrouter"
    CUSTOM = "custom"        # any other OpenAI-compatible endpoint


PROVIDER_KINDS: frozenset[str] = frozenset(k.value for k in ProviderKind)


class ModelSuggestion(BaseModel):
    id: str
    label: str
    vision: bool = False
    note: str = ""


class ProviderPreset(BaseModel):
    kind: ProviderKind
    label: str
    # How the model id is handed to LiteLLM: "<litellm_prefix>/<model id>".
    litellm_prefix: str
    default_api_base: str | None = None
    api_key_env: str | None = None
    # Environment variable that overrides default_api_base when Settings has none (e.g. a region- or
    # workspace-specific endpoint such as Model Studio Frankfurt's <workspace>.eu-central-1.maas.aliyuncs.com).
    api_base_env: str | None = None
    needs_key: bool = True
    # Structured output mode that works best with this provider (see LLMConfig.structured_output).
    structured_output: Literal["json", "json_schema"] = "json"
    local: bool = False
    models: list[ModelSuggestion] = []
    docs_url: str = ""


class ModelRef(BaseModel):
    provider: ProviderKind
    model: str

    @classmethod
    def parse(cls, ref: str) -> "ModelRef | None":
        """"openai:gpt-6-luna" → ModelRef; None when the prefix is not a known provider."""
        head, sep, tail = ref.partition(":")
        if not sep or head not in PROVIDER_KINDS or not tail.strip():
            return None
        return cls(provider=ProviderKind(head), model=tail.strip())

    def __str__(self) -> str:
        return f"{self.provider.value}:{self.model}"


class EnsembleMember(BaseModel):
    model: str                      # model reference
    weight: float = Field(default=1.0, gt=0.0, allow_inf_nan=False)
    label: str = ""                 # display name; defaults to the model reference

    @property
    def name(self) -> str:
        return self.label or self.model


type EnsembleMode = Literal["mixture", "vote"]


class EnsembleConfig(BaseModel):
    """A population of synthetic consumers driven by several models.

    - mixture: each customer is simulated end to end by one member, drawn with probability
      ∝ weight from a stable hash of (seed, persona id). Same seed ⇒ same assignment on every
      layout, so paired comparisons stay paired. Models the heterogeneity of a real population
      and averages out single-model quirks.
    - vote: every member answers each vision glance; the product named by most members wins and
      its interest is the members' mean (0 for members that picked something else). Text-only
      engines fall back to mixture.
    """
    members: list[EnsembleMember] = Field(min_length=1)
    mode: EnsembleMode = "mixture"
    seed: int = 0
