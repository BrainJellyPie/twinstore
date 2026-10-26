"""The local model plan says which rule chose the model and the memory it names, so the app can say why in the
reader's language; the English reason stays for older clients and logs."""

from pathlib import Path

import pytest

from store_emulator.application.hardware import GPUInfo, HardwareProfile, downgrade, recommend
from store_emulator.application.local_vlm import LocalVLMManager


def _hw(cores: int, ram_free: float, gpus: list[GPUInfo] | None = None) -> HardwareProfile:
    return HardwareProfile(os="linux", arch="x64", cpu="CPU", cores=cores, threads=cores, ram_gb=32, ram_free_gb=ram_free,
                           gpus=gpus or [])


@pytest.mark.parametrize(("cores", "free", "code"), [(8, 12, "cpu_reliable"), (4, 13.5, "cpu_fast"), (2, 1.5, "cpu_smallest")])
def test_cpu_plans_name_their_rule_and_free_memory(cores: int, free: float, code: str) -> None:
    plan = recommend(_hw(cores, free))
    assert plan.reason_code == code and plan.reason_gb == free
    assert f"{free:g} GB free memory" in plan.reason


def test_gpu_plans_name_their_rule_and_memory() -> None:
    nvidia = recommend(_hw(8, 12, [GPUInfo(vendor="nvidia", name="RTX", vram_gb=12, cuda="12.8")]))
    assert (nvidia.reason_code, nvidia.reason_gb) == ("nvidia", 12)
    vulkan = recommend(_hw(8, 12, [GPUInfo(vendor="amd", name="Radeon", vram_gb=8)]))
    assert (vulkan.reason_code, vulkan.reason_gb) == ("vulkan", 8)


def test_forced_model_does_not_advertise_the_original_automatic_recommendation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TWINSTORE_LOCAL_VLM_MODEL", "qwen3.5-2b")
    manager = LocalVLMManager(tmp_path, hardware=lambda: _hw(4, 13.5))
    _, plan = manager.plan()
    assert plan.model.key == "qwen3.5-2b"
    assert plan.reason == "set by TWINSTORE_LOCAL_VLM_MODEL=qwen3.5-2b"
    assert plan.reason_code is None


def test_gpu_fallback_keeps_the_failed_backend_in_the_displayed_reason() -> None:
    hw = _hw(8, 12, [GPUInfo(vendor="nvidia", name="RTX", vram_gb=12, cuda="12.8")])
    plan = downgrade(recommend(hw), hw)
    assert plan.backend == "cpu" and plan.reason.startswith("cuda did not start;")
    assert plan.reason_code is None
