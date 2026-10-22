"""Model providers (API keys, endpoints) and the models available to simulations."""

import urllib.error
import urllib.request
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from store_emulator.application import providers as provider_service
from store_emulator.application.providers import (
    ConnectionTest,
    ProviderStatus,
    ProviderUpdate,
)
from store_emulator.domain.providers import ProviderKind

router = APIRouter(prefix="/api", tags=["providers"])


class ModelOption(BaseModel):
    ref: str
    provider: str
    label: str
    vision: bool
    local: bool


class ConnectionTestRequest(BaseModel):
    model: str = Field(description='Model reference, e.g. "anthropic:claude-haiku-5-5"')
    vision: bool = Field(default=False, description="Also send a tiny image (checks vision support)")


@router.get("/providers", summary="Model providers and their connection status", response_model=list[ProviderStatus])
async def list_providers() -> list[ProviderStatus]:
    """Presets (suggested models, default endpoints) and whether a key is configured.
    Keys are never returned — only `has_key`, where it comes from, and its last 4 characters."""
    return await run_in_threadpool(_with_local_check, provider_service.list_providers())


_DIRECT = urllib.request.build_opener(urllib.request.ProxyHandler({}))   # 127.0.0.1 never goes through a proxy


def _listens(api_base: str) -> bool:
    """Something answers HTTP at this address (any status: llama.cpp, Ollama, LM Studio and vLLM all list models at
    …/models, and a 401 or 404 still proves a server)."""
    try:
        with _DIRECT.open(f"{api_base.rstrip('/')}/models", timeout=2):
            return True
    except urllib.error.HTTPError:
        return True
    except (OSError, ValueError):
        return False


def _with_local_check(statuses: list[ProviderStatus]) -> list[ProviderStatus]:
    """Whether each enabled local server on this computer answers."""
    def answers(status: ProviderStatus) -> bool | None:
        local = status.preset.local and status.enabled and status.api_base is not None
        if not local or urlsplit(status.api_base or "").hostname not in ("127.0.0.1", "localhost", "::1"):
            return None
        return _listens(status.api_base or "")
    return [status.model_copy(update={"answers": answers(status)}) for status in statuses]


@router.put("/providers/{kind}", summary="Save a provider's API key / endpoint", response_model=ProviderStatus)
async def update_provider(kind: str, update: ProviderUpdate) -> ProviderStatus:
    """Stored locally in `.data/settings/providers.json` (git-ignored, file mode 600).
    Send `api_key: ""` to remove a stored key."""
    try:
        provider = ProviderKind(kind)
    except ValueError:
        raise HTTPException(404, f"unknown provider: {kind}")
    return provider_service.update_provider(provider, update)


@router.post("/providers/test", summary="Test a model with a tiny request", response_model=ConnectionTest)
async def test_provider(req: ConnectionTestRequest) -> ConnectionTest:
    return await provider_service.test_connection(req.model, vision=req.vision)


@router.get("/models", summary="Model references usable now", response_model=list[ModelOption])
async def list_models() -> list[ModelOption]:
    """Every suggested model of every provider that is ready (key present, or local)."""
    return [ModelOption.model_validate(m) for m in provider_service.available_models()]
