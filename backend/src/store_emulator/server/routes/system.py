"""What runs the shoppers: cloud keys, this computer's hardware, the local vision model."""

from fastapi import APIRouter
from pydantic import BaseModel

from store_emulator.application.hardware import HardwareProfile, LocalVLMPlan
from store_emulator.application.local_vlm import LocalVLMStatus, manager
from store_emulator.application.providers import cloud_providers_with_key

router = APIRouter(prefix="/api/system", tags=["system"])


class ModelSetup(BaseModel):
    cloud_providers: list[str]          # providers with an API key
    warning: str | None                 # shown in the app while no key is set
    local: LocalVLMStatus
    hardware: HardwareProfile
    plan: LocalVLMPlan                  # the local model this computer gets


def _warning(cloud: list[str], local: LocalVLMStatus, plan: LocalVLMPlan) -> str | None:
    if cloud:
        return None
    model = f"{plan.model.label} on {plan.device}"
    if local.state == "ready":
        return (f"No API key is set. Vision shoppers run on a small local model ({model}): slower and less accurate "
                "than a cloud model. Add a key in Settings → Model providers.")
    if local.state in ("preparing", "downloading", "starting"):
        return (f"No API key is set. Setting up a local model for this computer ({model}): {local.message}. "
                "Rule-based runs work meanwhile; add a key in Settings → Model providers to skip this.")
    return ("No API key is set, so vision shoppers have no model to run on. Add a key in Settings → Model providers, "
            f"or start the local model ({model}).")


@router.get("/models", summary="Who runs the shoppers: cloud keys, local model, warning", response_model=ModelSetup)
def model_setup() -> ModelSetup:   # sync: hardware detection may call nvidia-smi
    mgr = manager()
    status = mgr.status()
    hw, plan = (status.hardware, status.plan) if status.hardware and status.plan else mgr.plan()
    cloud = cloud_providers_with_key()
    return ModelSetup(cloud_providers=cloud, warning=_warning(cloud, status, plan), local=status, hardware=hw, plan=plan)


@router.post("/local-model/start", summary="Download (if needed) and start the local vision model",
             response_model=LocalVLMStatus)
async def start_local_model() -> LocalVLMStatus:
    return manager().start()


@router.post("/local-model/stop", summary="Stop the local vision model started by TwinStore", response_model=LocalVLMStatus)
async def stop_local_model() -> LocalVLMStatus:
    manager().stop()
    return manager().status()
