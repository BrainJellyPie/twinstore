"""Model providers (API keys, endpoints) and the models available to simulations."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from store_emulator.application import providers as provider_service
from store_emulator.application.providers import ConnectionTest, ProviderStatus, ProviderUpdate
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
    return provider_service.list_providers()


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
