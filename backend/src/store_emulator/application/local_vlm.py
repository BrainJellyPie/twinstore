"""A local vision model for when no cloud model is set up: pick, fetch, serve.

With no API key, TwinStore's vision shoppers run on a small open model served by llama.cpp on this
computer. This module chooses the model for the hardware (`application/hardware.py`), downloads
the `llama-server` build that matches it (CUDA, Metal, Vulkan or CPU) from llama.cpp's GitHub
releases and the model from Hugging Face into `.data/local_vlm/`, starts the server on 127.0.0.1
and points the `llamacpp` provider at it, so `llamacpp:local` works in every model picker.

It starts on its own when the app is opened from a launcher (`TWINSTORE_LOCAL_VLM_AUTO=1`) and no
cloud key is set; otherwise from Settings or `POST /api/system/local-model/start`. Set
`TWINSTORE_LOCAL_VLM=off` to disable it, `TWINSTORE_LLAMA_SERVER=/path/to/llama-server` to use your
own build, `TWINSTORE_LOCAL_VLM_MODEL=<key>` to force a model (keys in `hardware.MODELS`).

A llama.cpp server that already answers on 127.0.0.1:8081 is used as it is.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import socket
import stat
import subprocess
import tarfile
import threading
import time
import urllib.request
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import IO, Literal, cast

from pydantic import BaseModel

from .hardware import (
    MODEL_BY_KEY,
    HardwareProfile,
    LocalVLMPlan,
    detect_hardware,
    downgrade,
    recommend,
)
from .storage.io import DATA_DIR

logger = logging.getLogger(__name__)

RELEASES_URL = "https://api.github.com/repos/ggml-org/llama.cpp/releases/latest"
HF_URL = "https://huggingface.co/{repo}/resolve/main/{file}"
DEFAULT_PORT = 8081
type State = Literal["off", "disabled", "preparing", "downloading", "starting", "ready", "error"]


class LocalVLMStatus(BaseModel):
    state: State = "off"
    message: str = ""
    progress: float | None = None     # current download, 0–1
    downloaded_mb: float = 0.0
    total_mb: float = 0.0
    plan: LocalVLMPlan | None = None
    hardware: HardwareProfile | None = None
    api_base: str | None = None
    model_ref: str = "llamacpp:local"
    managed: bool = False             # True: TwinStore started (and will stop) the server
    runtime: str = ""                 # llama.cpp build in use


# ── llama.cpp release assets ────────────────────────────────────────────────

def pick_runtime_assets(names: list[str], *, os_name: str, arch: str, backend: str, cuda: str = "") -> list[str]:
    """Release asset names to download for this machine, main archive first (CUDA builds also need
    the matching `cudart-…` archive on Windows and Linux). Falls back to the CPU build."""
    arch_tag = "x64" if arch == "x64" else "arm64"
    if os_name == "macos":
        pats = [rf"-bin-macos-{arch_tag}\.(?:tar\.gz|zip)$"]
    elif os_name == "windows":
        pats = {"cuda": [rf"-bin-win-cuda-([\d.]+)-{arch_tag}\.zip$"], "vulkan": [rf"-bin-win-vulkan-{arch_tag}\.zip$"]
                }.get(backend, []) + [rf"-bin-win-cpu-{arch_tag}\.zip$"]
    else:
        pats = {"cuda": [rf"-bin-ubuntu-cuda-([\d.]+)-{arch_tag}\.tar\.gz$"],
                "vulkan": [rf"-bin-ubuntu-vulkan-{arch_tag}\.tar\.gz$"]}.get(backend, []) + [rf"-bin-ubuntu-{arch_tag}\.tar\.gz$"]
    driver = tuple(int(x) for x in re.findall(r"\d+", cuda)[:2]) if cuda else (99, 99)
    for pat in pats:
        hits = [(n, re.search(pat, n)) for n in names if not n.startswith("cudart-")]
        hits = [(n, m) for n, m in hits if m]
        if not hits:
            continue
        if "cuda" in pat:
            # The newest CUDA build the driver supports.
            def ver(m: re.Match[str]) -> tuple[int, ...]:
                return tuple(int(x) for x in m.group(1).split("."))
            hits = [(n, m) for n, m in hits if ver(m)[:2] <= driver]
            if not hits:
                continue
            name, m = max(hits, key=lambda nm: ver(nm[1]))
            version = m.group(1)
            extra = [n for n in names if n.startswith("cudart-") and f"cuda-{version}-{arch_tag}" in n]
            return [name, *extra[:1]]
        return [hits[0][0]]
    return []


def _safe_extract(archive: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    if archive.name.endswith(".zip"):
        with zipfile.ZipFile(archive) as z:
            for member in z.infolist():
                target = (dest / member.filename).resolve()
                if not str(target).startswith(str(dest.resolve())):
                    raise ValueError(f"unsafe path in archive: {member.filename}")
            z.extractall(dest)
    else:
        with tarfile.open(archive) as t:
            t.extractall(dest, filter="data")


def _find_server(root: Path) -> Path | None:
    for name in ("llama-server.exe", "llama-server"):
        found = sorted(root.rglob(name))
        if found:
            return found[0]
    return None


# ── the manager ─────────────────────────────────────────────────────────────

class LocalVLMManager:
    def __init__(self, home: Path | None = None, *, opener: Callable[[urllib.request.Request], IO[bytes]] | None = None,
                 hardware: Callable[[], HardwareProfile] = detect_hardware) -> None:
        self.home = home or Path(DATA_DIR) / "local_vlm"
        self._open: Callable[[urllib.request.Request], IO[bytes]] = opener or _urlopen
        self._hardware = hardware
        self._hw: HardwareProfile | None = None
        self._status = LocalVLMStatus(state="disabled" if self.disabled else "off")
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._proc: subprocess.Popen[bytes] | None = None

    @property
    def disabled(self) -> bool:
        return os.environ.get("TWINSTORE_LOCAL_VLM", "").lower() in ("0", "off", "false", "no")

    def status(self) -> LocalVLMStatus:
        with self._lock:
            if self._status.state == "ready" and self._proc is not None and self._proc.poll() is not None:
                self._status = self._status.model_copy(update={"state": "error", "message": "the local model server stopped"})
            return self._status.model_copy()

    def _set(self, **changes: object) -> None:
        with self._lock:
            self._status = self._status.model_copy(update=changes)

    def plan(self) -> tuple[HardwareProfile, LocalVLMPlan]:
        if self._hw is None:            # detected once per process
            self._hw = self._hardware()
        hw = self._hw
        plan = recommend(hw)
        forced = os.environ.get("TWINSTORE_LOCAL_VLM_MODEL", "")
        if forced in MODEL_BY_KEY:
            plan = plan.model_copy(update={"model": MODEL_BY_KEY[forced], "reason": f"set by TWINSTORE_LOCAL_VLM_MODEL={forced}"})
        return hw, plan

    def start(self, *, wait: bool = False) -> LocalVLMStatus:
        """Prepare and start the local model in the background (no-op while already running)."""
        if self.disabled:
            self._set(state="disabled", message="turned off by TWINSTORE_LOCAL_VLM")
            return self.status()
        with self._lock:
            busy = self._thread is not None and self._thread.is_alive()
            ready = self._status.state == "ready" and (self._proc is None or self._proc.poll() is None)
        if not busy and not ready:
            self._thread = threading.Thread(target=self._run, name="local-vlm", daemon=True)
            self._thread.start()
        if wait and self._thread is not None:
            self._thread.join()
        return self.status()

    def stop(self) -> None:
        proc = self._proc
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
        self._proc = None
        if self._status.managed:
            self._set(state="off", message="stopped", managed=False)

    # ── pipeline ──

    def _run(self) -> None:
        try:
            self._set(state="preparing", message="Reading this computer's hardware", progress=None)
            hw, plan = self.plan()
            self._set(hardware=hw, plan=plan)
            if self._answers(DEFAULT_PORT):   # someone already serves a model there (e.g. by hand)
                self._ready(f"http://127.0.0.1:{DEFAULT_PORT}/v1", managed=False, runtime="already running")
                return
            server = self._runtime(hw, plan)
            files = [self._download_model(plan.model.repo, f) for f in (plan.model.file, plan.model.mmproj)]
            try:
                self._serve(server, files[0], files[1], plan)
            except RuntimeError as e:
                if plan.backend == "cpu":
                    raise
                logger.warning(f"[local_vlm] {plan.backend} build did not start ({e}); falling back to the CPU")
                plan = downgrade(plan, hw)
                self._set(plan=plan)
                server = self._runtime(hw, plan)
                files = [self._download_model(plan.model.repo, f) for f in (plan.model.file, plan.model.mmproj)]
                self._serve(server, files[0], files[1], plan)
        except Exception as e:  # noqa: BLE001 — surfaced in the status, the app keeps working without it
            logger.warning(f"[local_vlm] {type(e).__name__}: {e}")
            self._set(state="error", message=f"{type(e).__name__}: {e}"[:300], progress=None)

    def _answers(self, port: int) -> bool:
        """Is a llama.cpp server ready on this port? Never through a proxy: HTTP(S)_PROXY settings would
        send 127.0.0.1 to the proxy."""
        try:
            with _DIRECT.open(f"http://127.0.0.1:{port}/health", timeout=3) as r:
                return getattr(r, "status", 200) == 200
        except Exception:  # noqa: BLE001 — nothing listening, or still loading
            return False

    def _runtime(self, hw: HardwareProfile, plan: LocalVLMPlan) -> Path:
        own = os.environ.get("TWINSTORE_LLAMA_SERVER")
        if own and Path(own).is_file():
            self._set(runtime=own)
            return Path(own)
        target = self.home / "bin" / plan.backend
        found = _find_server(target) if target.exists() else None
        if found is None and shutil.which("llama-server"):   # installed by the user (brew, winget, a build)
            found = Path(str(shutil.which("llama-server")))
        if found is not None:
            self._set(runtime=str(found))
            return found
        self._set(state="downloading", message=f"Getting llama.cpp for {plan.backend.upper()}")
        try:
            with self._open(urllib.request.Request(RELEASES_URL, headers={"Accept": "application/vnd.github+json",
                                                                          "User-Agent": "TwinStore"})) as r:
                release = json.loads(r.read().decode())
        except OSError as e:
            raise RuntimeError(
                f"could not reach GitHub to download llama.cpp ({e}). Install llama.cpp (e.g. `brew install llama.cpp`, "
                "`winget install llama.cpp`) so that `llama-server` is on the PATH, or set TWINSTORE_LLAMA_SERVER "
                "to its path, then start the local model again") from e
        assets = {a["name"]: a["browser_download_url"] for a in release.get("assets", [])}
        gpu = hw.best_gpu
        names = pick_runtime_assets(list(assets), os_name=hw.os, arch=hw.arch, backend=plan.backend,
                                    cuda=gpu.cuda if gpu else "")
        if not names:
            raise RuntimeError(f"no llama.cpp build for {hw.os}/{hw.arch} in release {release.get('tag_name')}")
        target.mkdir(parents=True, exist_ok=True)
        for name in names:
            archive = self._download(assets[name], target / name, label=f"llama.cpp {release.get('tag_name', '')}")
            _safe_extract(archive, target)
            archive.unlink(missing_ok=True)
        found = _find_server(target)
        if found is None:
            raise RuntimeError("llama-server not found in the downloaded build")
        if os.name != "nt":
            for exe in found.parent.iterdir():
                if exe.is_file() and not exe.suffix:
                    exe.chmod(exe.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        self._set(runtime=f"{release.get('tag_name', '')} {names[0]}")
        return found

    def _download_model(self, repo: str, file: str) -> Path:
        path = self.home / "models" / repo.replace("/", "__") / file
        if path.is_file() and path.stat().st_size > 0:
            return path
        return self._download(HF_URL.format(repo=repo, file=file), path, label=file)

    def _download(self, url: str, path: Path, *, label: str) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        part = path.with_name(path.name + ".part")
        self._set(state="downloading", message=f"Downloading {label}", progress=0.0, downloaded_mb=0.0, total_mb=0.0)
        try:
            with self._open(urllib.request.Request(url, headers={"User-Agent": "TwinStore"})) as r, part.open("wb") as out:
                length = getattr(r, "headers", {}).get("Content-Length")
                total = int(length) if length is not None else None
                done = 0
                last = 0.0
                while chunk := r.read(1 << 20):
                    out.write(chunk)
                    done += len(chunk)
                    if time.monotonic() - last > 0.5:
                        last = time.monotonic()
                        self._set(progress=min(done / total, 1.0) if total else None, downloaded_mb=round(done / 1e6, 1),
                                  total_mb=round(total / 1e6, 1) if total else 0.0)
            if done == 0 or (total is not None and done != total):
                raise RuntimeError(f"Download of {label} is incomplete: received {done} bytes, expected {total if total is not None else 'a nonempty file'}")
            part.replace(path)
        finally:
            part.unlink(missing_ok=True)
        self._set(progress=1.0, downloaded_mb=round(done / 1e6, 1))
        return path

    def _serve(self, server: Path, model: Path, mmproj: Path, plan: LocalVLMPlan) -> None:
        port = DEFAULT_PORT if _port_free(DEFAULT_PORT) else _free_port()
        self._set(state="starting", message=f"Starting {plan.model.label} on {plan.device}", progress=None)
        cmd = [str(server), "-m", str(model), "--mmproj", str(mmproj), "--host", "127.0.0.1", "--port", str(port),
               "-c", str(plan.context), "-np", str(plan.parallel), "-ngl", str(plan.gpu_layers), "-t", str(plan.threads),
               "--reasoning", "off", "--image-max-tokens", "512", "--cache-ram", "256", "--no-webui", "-a", "local-model"]
        log = (self.home / "server.log").open("ab")
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self._proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                      creationflags=flags)
        deadline = time.monotonic() + 600
        while time.monotonic() < deadline:
            if self._proc.poll() is not None:
                raise RuntimeError(f"llama-server exited with code {self._proc.returncode} (see {self.home / 'server.log'})")
            if self._answers(port):
                self._ready(f"http://127.0.0.1:{port}/v1", managed=True, runtime=self._status.runtime)
                return
            time.sleep(1.0)
        self.stop()
        raise RuntimeError("the local model did not load within 10 minutes")

    def _ready(self, api_base: str, *, managed: bool, runtime: str) -> None:
        from . import providers  # late import: providers imports nothing from here

        providers.use_local_server(api_base)
        plan = self._status.plan
        label = f"{plan.model.label} on {plan.device}" if plan and managed else "the llama.cpp server on this computer"
        self._set(state="ready", message=f"Ready: {label}", api_base=api_base, managed=managed, runtime=runtime,
                  progress=None)
        logger.info(f"[local_vlm] ready at {api_base} ({label})")


_DIRECT = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _urlopen(req: urllib.request.Request) -> IO[bytes]:
    return cast(IO[bytes], urllib.request.urlopen(req, timeout=60))


def _port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


_manager: list[LocalVLMManager] = []


def manager() -> LocalVLMManager:
    """The process-wide manager (one local model server per app)."""
    if not _manager:
        _manager.append(LocalVLMManager())
    return _manager[0]
