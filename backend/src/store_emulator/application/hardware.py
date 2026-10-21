"""What this computer can run: CPU, memory and GPU, and the local vision model that fits.

Used when no cloud model is configured: TwinStore then runs its shoppers on a small open
vision-language model served by llama.cpp on this machine (`application/local_vlm.py`). The choice
trades reading accuracy against speed and memory:

| Model (Q4_K_M + projector) | download | memory |
|---|---|---|
| LFM2.5-VL-450M | 0.33 GB | ~0.8 GB |
| Qwen3.5-0.8B | 0.74 GB | ~1.4 GB |
| Qwen3.5-2B | 1.95 GB | ~2.8 GB |
| Qwen3.5-4B | 3.4 GB | ~4.6 GB |
| Qwen3.5-9B | 6.6 GB | ~8 GB |

On 2 CPU cores the two smallest take 7–18 s per decision and read product names and prices poorly;
Qwen3.5-2B reads them reliably but takes ~22.5 s per glance (README). So a CPU
gets the 2B model only with enough cores, and the 4B and 9B models only run on a GPU.

Detection never raises: anything that cannot be read is left at a conservative default, and every
external command runs with a short timeout.
"""

from __future__ import annotations

import ctypes
import json
import logging
import os
import platform
import re
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Literal, cast

from pydantic import BaseModel

logger = logging.getLogger(__name__)

type Backend = Literal["cuda", "metal", "vulkan", "cpu"]
type Runner = Callable[[list[str]], str]


class GPUInfo(BaseModel):
    vendor: Literal["nvidia", "amd", "intel", "apple", "other"]
    name: str
    vram_gb: float = 0.0          # dedicated memory; Apple silicon: unified memory
    cuda: str = ""                # highest CUDA version the NVIDIA driver supports, e.g. "12.8"


class HardwareProfile(BaseModel):
    os: Literal["windows", "macos", "linux", "other"]
    arch: Literal["x64", "arm64", "other"]
    cpu: str = ""
    cores: int = 1                # physical cores (best effort)
    threads: int = 1              # logical processors
    ram_gb: float = 0.0
    ram_free_gb: float = 0.0
    gpus: list[GPUInfo] = []

    @property
    def best_gpu(self) -> GPUInfo | None:
        usable = [g for g in self.gpus if g.vendor in ("nvidia", "apple", "amd") or g.vram_gb >= 3]
        return max(usable, key=lambda g: g.vram_gb, default=None)


class LocalModel(BaseModel):
    key: str
    label: str
    repo: str                     # Hugging Face repository
    file: str
    mmproj: str                   # vision projector in the same repository
    download_gb: float
    memory_gb: float              # model + projector + a 8k context, rounded up


class LocalVLMPlan(BaseModel):
    backend: Backend
    model: LocalModel
    device: str                   # what it runs on, for people
    gpu_layers: int               # llama.cpp -ngl
    threads: int
    parallel: int                 # llama.cpp -np: concurrent shoppers
    context: int
    reason: str


MODELS: list[LocalModel] = [
    LocalModel(key="lfm2.5-vl-450m", label="LFM2.5-VL-450M", repo="LiquidAI/LFM2.5-VL-450M-GGUF",
               file="LFM2.5-VL-450M-Q4_K_M.gguf", mmproj="mmproj-LFM2.5-VL-450m-Q8_0.gguf", download_gb=0.33, memory_gb=0.8),
    LocalModel(key="qwen3.5-0.8b", label="Qwen3.5-0.8B", repo="unsloth/Qwen3.5-0.8B-GGUF",
               file="Qwen3.5-0.8B-Q4_K_M.gguf", mmproj="mmproj-F16.gguf", download_gb=0.74, memory_gb=1.4),
    LocalModel(key="qwen3.5-2b", label="Qwen3.5-2B", repo="unsloth/Qwen3.5-2B-GGUF",
               file="Qwen3.5-2B-Q4_K_M.gguf", mmproj="mmproj-F16.gguf", download_gb=1.95, memory_gb=2.8),
    LocalModel(key="qwen3.5-4b", label="Qwen3.5-4B", repo="unsloth/Qwen3.5-4B-GGUF",
               file="Qwen3.5-4B-Q4_K_M.gguf", mmproj="mmproj-F16.gguf", download_gb=3.41, memory_gb=4.6),
    LocalModel(key="qwen3.5-9b", label="Qwen3.5-9B", repo="unsloth/Qwen3.5-9B-GGUF",
               file="Qwen3.5-9B-Q4_K_M.gguf", mmproj="mmproj-F16.gguf", download_gb=6.6, memory_gb=8.0),
]
MODEL_BY_KEY = {m.key: m for m in MODELS}


# ── detection ───────────────────────────────────────────────────────────────

def _run(cmd: list[str]) -> str:
    """stdout of a command, or "" if it is missing, fails or takes more than 5 s."""
    if not shutil.which(cmd[0]):
        return ""
    try:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        done = subprocess.run(cmd, capture_output=True, text=True, timeout=5, check=False, creationflags=flags)
    except (OSError, subprocess.SubprocessError):
        return ""
    return done.stdout if done.returncode == 0 else ""


def _os() -> Literal["windows", "macos", "linux", "other"]:
    name = platform.system().lower()
    return "windows" if name == "windows" else "macos" if name == "darwin" else "linux" if name == "linux" else "other"


def _arch() -> Literal["x64", "arm64", "other"]:
    machine = platform.machine().lower()
    if machine in ("x86_64", "amd64", "x64"):
        return "x64"
    if machine in ("arm64", "aarch64"):
        return "arm64"
    return "other"


def _linux_memory(meminfo: str) -> tuple[float, float]:
    vals = {k: int(v) for k, v in re.findall(r"^(\w+):\s+(\d+) kB", meminfo, re.MULTILINE)}
    total = vals.get("MemTotal", 0) / 1024**2
    free = vals.get("MemAvailable", vals.get("MemFree", 0)) / 1024**2
    return round(total, 1), round(free, 1)


def _linux_physical_cores(cpuinfo: str) -> int:
    pairs = set(re.findall(r"physical id\s*:\s*(\d+).*?core id\s*:\s*(\d+)", cpuinfo, re.DOTALL))
    return len(pairs)


def _windows_memory() -> tuple[float, float]:
    class _Status(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
    status = _Status()
    status.dwLength = ctypes.sizeof(_Status)
    windll = getattr(ctypes, "windll", None)
    if windll is None or not windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return 0.0, 0.0
    return round(status.ullTotalPhys / 1024**3, 1), round(status.ullAvailPhys / 1024**3, 1)


def parse_nvidia_smi(query_csv: str, header: str) -> list[GPUInfo]:
    """`nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits` + the plain header."""
    m = re.search(r"CUDA Version:\s*([\d.]+)", header)
    cuda = m.group(1) if m else ""
    gpus: list[GPUInfo] = []
    for line in query_csv.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 2 and parts[1].replace(".", "").isdigit():
            gpus.append(GPUInfo(vendor="nvidia", name=parts[0], vram_gb=round(float(parts[1]) / 1024, 1), cuda=cuda))
    return gpus


def _linux_drm_gpus(root: Path = Path("/sys/class/drm")) -> list[GPUInfo]:
    """AMD / Intel GPUs from sysfs (NVIDIA comes from nvidia-smi)."""
    out: list[GPUInfo] = []
    for card in sorted(root.glob("card[0-9]")):
        try:
            vendor_id = (card / "device" / "vendor").read_text().strip()
        except OSError:
            continue
        vendor = {"0x1002": "amd", "0x8086": "intel"}.get(vendor_id)
        if vendor is None:
            continue
        vram = 0.0
        try:
            vram = int((card / "device" / "mem_info_vram_total").read_text()) / 1024**3
        except (OSError, ValueError):
            pass
        out.append(GPUInfo(vendor=vendor, name=f"{vendor.upper()} GPU ({card.name})", vram_gb=round(vram, 1)))  # type: ignore[arg-type]
    return out


def _windows_gpus(run: Runner) -> list[GPUInfo]:
    raw = run(["powershell", "-NoProfile", "-Command",
               "Get-CimInstance Win32_VideoController | Select-Object Name,AdapterRAM | ConvertTo-Json"])
    try:
        data: object = json.loads(raw) if raw.strip() else []
    except ValueError:
        return []
    items = cast(list[object], data) if isinstance(data, list) else [data]
    out: list[GPUInfo] = []
    for raw_item in items:
        if not isinstance(raw_item, dict):
            continue
        item = cast(dict[str, object], raw_item)
        name = str(item.get("Name") or "")
        low = name.lower()
        vendor = "nvidia" if "nvidia" in low else "amd" if ("amd" in low or "radeon" in low) else "intel" if "intel" in low else "other"
        # AdapterRAM is a 32-bit field (caps at 4 GB): a lower bound only.
        adapter = item.get("AdapterRAM")
        vram = float(adapter) / 1024**3 if isinstance(adapter, (int, float)) else 0.0
        if vendor != "nvidia":    # NVIDIA cards come from nvidia-smi with their real memory
            out.append(GPUInfo(vendor=vendor, name=name, vram_gb=round(vram, 1)))  # type: ignore[arg-type]
    return out


def detect_hardware(run: Runner = _run) -> HardwareProfile:
    os_name, arch = _os(), _arch()
    threads = os.cpu_count() or 1
    cpu, cores, ram, ram_free = platform.processor() or "", 0, 0.0, 0.0
    gpus: list[GPUInfo] = []
    try:
        if os_name == "linux":
            cpuinfo = Path("/proc/cpuinfo").read_text(errors="ignore") if Path("/proc/cpuinfo").exists() else ""
            m = re.search(r"model name\s*:\s*(.+)", cpuinfo)
            cpu = m.group(1).strip() if m else cpu
            cores = _linux_physical_cores(cpuinfo)
            if Path("/proc/meminfo").exists():
                ram, ram_free = _linux_memory(Path("/proc/meminfo").read_text())
            gpus += _linux_drm_gpus()
        elif os_name == "macos":
            cpu = run(["sysctl", "-n", "machdep.cpu.brand_string"]).strip() or cpu
            cores = int(run(["sysctl", "-n", "hw.physicalcpu"]).strip() or 0)
            ram = round(int(run(["sysctl", "-n", "hw.memsize"]).strip() or 0) / 1024**3, 1)
            pages = re.findall(r"Pages (?:free|inactive|speculative):\s+(\d+)", run(["vm_stat"]))
            page = 16384 if arch == "arm64" else 4096
            ram_free = round(sum(int(p) for p in pages) * page / 1024**3, 1) if pages else ram * 0.5
            if arch == "arm64":
                gpus.append(GPUInfo(vendor="apple", name=f"{cpu or 'Apple silicon'} GPU", vram_gb=ram))
        elif os_name == "windows":
            ram, ram_free = _windows_memory()
            raw = run(["powershell", "-NoProfile", "-Command",
                       "(Get-CimInstance Win32_Processor | Measure-Object -Property NumberOfCores -Sum).Sum"]).strip()
            cores = int(raw) if raw.isdigit() else 0
            gpus += _windows_gpus(run)
        nvidia = parse_nvidia_smi(run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"]),
                                  run(["nvidia-smi"]))
        gpus = nvidia + [g for g in gpus if g.vendor != "nvidia"]
    except Exception as e:  # noqa: BLE001 — detection is best effort; defaults are conservative
        logger.info(f"[hardware] detection incomplete: {type(e).__name__}: {e}")
    return HardwareProfile(os=os_name, arch=arch, cpu=cpu, cores=cores or max(1, threads // 2), threads=threads,
                           ram_gb=ram, ram_free_gb=ram_free or ram * 0.5, gpus=gpus)


# ── recommendation ──────────────────────────────────────────────────────────

def _largest_fitting(budget_gb: float, cap: str | None = None) -> LocalModel:
    allowed = MODELS if cap is None else MODELS[: [m.key for m in MODELS].index(cap) + 1]
    fitting = [m for m in allowed if m.memory_gb <= budget_gb]
    return fitting[-1] if fitting else MODELS[0]


def recommend(hw: HardwareProfile) -> LocalVLMPlan:
    """The best local vision model this machine runs at a usable speed, and how to run it."""
    gpu = hw.best_gpu
    if gpu is not None and gpu.vendor == "nvidia" and hw.arch in ("x64", "arm64") and gpu.vram_gb >= 2:
        model = _largest_fitting(gpu.vram_gb * 0.85)
        return LocalVLMPlan(backend="cuda", model=model, device=f"{gpu.name} ({gpu.vram_gb:g} GB)", gpu_layers=999,
                            threads=max(1, hw.cores), parallel=4 if gpu.vram_gb >= 8 else 2, context=16384,
                            reason=f"NVIDIA GPU with {gpu.vram_gb:g} GB: the largest model that fits in 85 % of it")
    if gpu is not None and gpu.vendor == "apple":
        model = _largest_fitting(hw.ram_gb * 0.45)
        return LocalVLMPlan(backend="metal", model=model, device=f"{gpu.name} ({hw.ram_gb:g} GB unified memory)",
                            gpu_layers=999, threads=max(1, hw.cores), parallel=2, context=8192,
                            reason=f"Apple silicon: Metal, at most 45 % of {hw.ram_gb:g} GB unified memory")
    if gpu is not None and gpu.vendor in ("amd", "intel", "other") and gpu.vram_gb >= 3:
        model = _largest_fitting(gpu.vram_gb * 0.8, cap="qwen3.5-4b")
        return LocalVLMPlan(backend="vulkan", model=model, device=f"{gpu.name} ({gpu.vram_gb:g} GB)", gpu_layers=999,
                            threads=max(1, hw.cores), parallel=2, context=8192,
                            reason=f"{gpu.vendor.upper()} GPU with {gpu.vram_gb:g} GB: Vulkan")
    # CPU: speed decides. 2B reads products far better but takes ~2.4× as long per glance.
    free = hw.ram_free_gb or hw.ram_gb * 0.5
    if hw.cores >= 8 and free >= 6:
        key, why = "qwen3.5-2b", f"{hw.cores} CPU cores and {free:g} GB free memory: the 2B model reads labels reliably"
    elif hw.cores >= 3 and free >= 2:
        key, why = "qwen3.5-0.8b", f"{hw.cores} CPU cores and {free:g} GB free memory: the 0.8B model keeps runs fast"
    else:
        key, why = "lfm2.5-vl-450m", f"{hw.cores} CPU core(s) and {free:g} GB free memory: the smallest model"
    return LocalVLMPlan(backend="cpu", model=MODEL_BY_KEY[key], device=f"CPU, {hw.cores} cores, {hw.ram_gb:g} GB",
                        gpu_layers=0, threads=max(1, hw.cores), parallel=1, context=8192, reason=why)


def downgrade(plan: LocalVLMPlan, hw: HardwareProfile) -> LocalVLMPlan:
    """The CPU plan, for when a GPU build does not start (missing driver, too old a GPU)."""
    cpu_only = hw.model_copy(update={"gpus": []})
    out = recommend(cpu_only)
    return out.model_copy(update={"reason": f"{plan.backend} did not start; {out.reason}"})
