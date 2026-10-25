"""A local vision model for when no cloud model is set up: pick, fetch, serve.

With no API key, TwinStore's vision shoppers run on a small open model served by llama.cpp on this
computer. This module chooses the model for the hardware (`application/hardware.py`), downloads
the `llama-server` build that matches it (CUDA, Metal, Vulkan or CPU) from llama.cpp's GitHub
releases and the model from Hugging Face into `.data/local_vlm/`, starts the server on 127.0.0.1
and points the `llamacpp` provider at it, so `llamacpp:local` works in every model picker.

Nothing is downloaded until the user starts it (Settings, or `POST /api/system/local-model/start`), which also
records that choice. When the app is opened from a launcher (`TWINSTORE_LOCAL_VLM_AUTO=1`) and no cloud key is set,
it starts again on its own if the user chose it before, or if it is already on this computer (an earlier version
downloaded it without asking); it never downloads on its own, and once the user stops it, it stays off. Set
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
import sys
import tarfile
import threading
import time
import urllib.error
import urllib.request
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import IO, Literal, cast
from urllib.parse import urlsplit

from pydantic import BaseModel

from store_emulator.engine.files import remove_tree, replace_file

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

# Recent releases, newest first. "latest" is not enough: llama.cpp's versioned releases (v0.7.0, …) carry no
# binaries, which come with its numbered builds (b11804, …) marked as pre-releases.
RELEASES_URL = "https://api.github.com/repos/ggml-org/llama.cpp/releases?per_page=30"
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
    slots: int = 0                    # requests the server answers at once (llama.cpp -np); 0 = not known
    runtime: str = ""                 # llama.cpp build in use
    downloaded: bool = False          # the planned model and a llama.cpp build are on this computer (no download)


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
            for name, m in sorted(hits, key=lambda nm: ver(nm[1]), reverse=True):
                version = m.group(1)
                extra = [n for n in names if n.startswith("cudart-") and re.search(pat, n)
                         and f"cuda-{version}-{arch_tag}" in n]
                if extra:
                    return [name, extra[0]]
            continue  # An incomplete CUDA pair cannot run; try the CPU build.
        return [hits[0][0]]
    return []


def pick_release(
    releases: list[dict[str, object]], *, os_name: str, arch: str, backend: str, cuda: str = "",
) -> tuple[str, list[str], dict[str, str]] | None:
    """The newest compatible build, preferring the requested GPU across recent releases before CPU fallback.
    Return (tag, asset names to download, every asset's URL); skip drafts and releases without binaries."""
    fallback: tuple[str, list[str], dict[str, str]] | None = None
    for release in releases:
        if release.get("draft"):
            continue
        raw = release.get("assets")
        assets: dict[str, str] = {}
        for asset in cast(list[object], raw) if isinstance(raw, list) else []:
            if isinstance(asset, dict):
                item = cast(dict[str, object], asset)
                name, url = item.get("name"), item.get("browser_download_url")
                if isinstance(name, str) and isinstance(url, str):
                    assets[name] = url
        names = pick_runtime_assets(list(assets), os_name=os_name, arch=arch, backend=backend, cuda=cuda)
        if names:
            chosen = str(release.get("tag_name", "")), names, assets
            if backend in ("cuda", "vulkan") and f"-{backend}-" not in names[0]:
                # Assets arrive separately: a new CPU archive must not hide an older usable GPU build.
                if fallback is None:
                    fallback = chosen
                continue
            return chosen
    return fallback


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


def _place_cuda_libraries(target: Path, server: Path) -> None:
    """CUDA archives may have their own wrapper directory; loaders search beside the executable."""
    pattern = r"(?:lib(?:cudart|cublas|cublasLt)\.so(?:\.\d+)*|(?:cudart|cublas|cublasLt)64_\d+\.dll)"
    for library in sorted(target.rglob("*")):
        if library.parent == server.parent or re.fullmatch(pattern, library.name) is None:
            continue
        if not (library.is_file() or library.is_symlink()):
            continue
        destination = server.parent / library.name
        if not destination.exists() and not destination.is_symlink():
            replace_file(library, destination)


# ── the manager ─────────────────────────────────────────────────────────────

class _StartCancelled(Exception):
    """The user stopped this startup before the model was ready."""


class _NoGpuBuild(Exception):
    """The newest llama.cpp releases have no build for this GPU (or its driver): the CPU plan applies."""


class _NeedsDownload(Exception):
    """A start nobody asked for reached a download: it stops there."""


# The user's own Start (True) or Stop (False) in the app; no file: never asked.
_CHOICE = "choice.json"
NOT_DOWNLOADED = "not downloaded yet: Start downloads it"


# Written into bin/<backend> once every archive of a build is unpacked; a build without it (an interrupted download, a
# full disk, a DLL removed by antivirus) is fetched again rather than reused forever.
_COMPLETE = ".complete"


def _unpacked_before_marker(target: Path, backend: str) -> bool:
    """A whole build that versions before 0.4.3 unpacked: they wrote no marker, but removed each archive once it was
    unpacked (and a download cut short left its .part). Removing it would leave a computer without internet access (a
    company network) with no local model. Whole: llama-server is there (runnable), no download or archive was left
    mid-way, and a CUDA build has the CUDA runtime it is fetched with."""
    if not target.is_dir() or any(p.name.endswith((".part", ".zip", ".tar.gz")) for p in target.iterdir()):
        return False
    server = _find_server(target)
    if server is None or (os.name != "nt" and not os.access(server, os.X_OK)):
        return False
    return backend != "cuda" or any("cudart" in p.name for p in target.rglob("*"))


class LocalVLMManager:
    def __init__(self, home: Path | None = None, *, opener: Callable[[urllib.request.Request], IO[bytes]] | None = None,
                 hardware: Callable[[], HardwareProfile] = detect_hardware) -> None:
        self.home = home or Path(DATA_DIR) / "local_vlm"
        self._open: Callable[[urllib.request.Request], IO[bytes]] = opener or _urlopen
        self._hardware = hardware
        self._hw: HardwareProfile | None = None
        self._status = LocalVLMStatus(state="disabled" if self.disabled else "off")
        self._lock = threading.Lock()
        self._plan_lock = threading.Lock()   # one hardware probe at a time (the start thread and /api/system/models)
        self._choice_lock = threading.Lock()
        self._choice: bool | None = None  # Start/Stop survives failed persistence for the current session.
        self._cancel = threading.Event()
        self._stopping = False
        self._thread: threading.Thread | None = None
        self._proc: subprocess.Popen[bytes] | None = None
        self._may_download = True

    @property
    def disabled(self) -> bool:
        return os.environ.get("TWINSTORE_LOCAL_VLM", "").lower() in ("0", "off", "false", "no")

    def status(self, *, check_external: bool = False) -> LocalVLMStatus:
        with self._lock:
            if self._status.state == "ready" and self._proc is not None and self._proc.poll() is not None:
                self._status = self._status.model_copy(update={"state": "error", "message": "the local model server stopped"})
            checked = self._status
        # An adopted server has no process handle to poll. Check it at explicit
        # status refresh/start boundaries, outside the lock and off the hot path.
        if (check_external and checked.state == "ready" and not checked.managed and checked.api_base
                and not server_answers(checked.api_base)):
            with self._lock:
                if self._status is checked:
                    self._status = checked.model_copy(update={
                        "state": "error", "message": "the external local model server is unavailable"})
        with self._lock:
            return self._status.model_copy()

    def _set(self, **changes: object) -> None:
        with self._lock:
            if not self._cancel.is_set() or changes.get("state") == "disabled":
                self._status = self._status.model_copy(update=changes)

    def _check_cancelled(self) -> None:
        if self._cancel.is_set():
            raise _StartCancelled

    def plan(self) -> tuple[HardwareProfile, LocalVLMPlan]:
        with self._plan_lock:
            if self._hw is None:            # detected once per process
                self._hw = self._hardware()
            hw = self._hw
        plan = recommend(hw)
        forced = os.environ.get("TWINSTORE_LOCAL_VLM_MODEL", "")
        if forced in MODEL_BY_KEY:
            plan = plan.model_copy(update={"model": MODEL_BY_KEY[forced], "reason": f"set by TWINSTORE_LOCAL_VLM_MODEL={forced}"})
        return hw, plan

    # ── the user's choice ──

    def chosen(self) -> bool | None:
        """True: the user started the local model; False: they stopped it; None: they never did either."""
        with self._choice_lock:
            if self._choice is not None:
                return self._choice
            try:
                raw: object = json.loads((self.home / _CHOICE).read_text(encoding="utf-8"))
            except (OSError, ValueError):       # never chosen, or a file cut short: as if never asked
                return None
            use = cast(dict[str, object], raw).get("use") if isinstance(raw, dict) else None
            return use if isinstance(use, bool) else None

    def choose(self, use: bool) -> None:
        """Remember the user's Start or Stop for the next time the app opens."""
        with self._choice_lock:
            with self._lock:
                self._choice = use
            path = self.home / _CHOICE
            tmp = path.with_name(f"{_CHOICE}.{os.getpid()}.tmp")
            try:
                self.home.mkdir(parents=True, exist_ok=True)
                tmp.write_text(json.dumps({"use": use}), encoding="utf-8")
                replace_file(tmp, path)
            except OSError:                     # a read-only folder: the choice holds for this session only
                logger.warning("[local_vlm] could not save the local model choice", exc_info=True)
                try:
                    tmp.unlink(missing_ok=True)
                except OSError:
                    pass  # The pending Start/Stop must still reach the model process.

    def on_disk(self, plan: LocalVLMPlan) -> bool:
        """Would this plan start without downloading anything?"""
        own = os.environ.get("TWINSTORE_LLAMA_SERVER")
        target = self.home / "bin" / plan.backend
        runtime = bool(own and Path(own).is_file()) or (
            ((target / _COMPLETE).is_file() or _unpacked_before_marker(target, plan.backend))
            and _find_server(target) is not None)
        models = self.home / "models" / plan.model.repo.replace("/", "__")
        return runtime and all((models / f).is_file() and (models / f).stat().st_size > 0
                               for f in (plan.model.file, plan.model.mmproj))

    def auto_start(self) -> bool:
        """A start nobody asked for (the app opening, a request with no key): only what the user set up. It downloads
        only for a user who chose the local model (an interrupted download goes on); for anyone else it starts a model
        that is already on this computer, or nothing. False: nothing is coming."""
        if self.disabled:
            self._set(state="disabled", message="turned off by TWINSTORE_LOCAL_VLM")
            return False
        choice = self.chosen()
        if choice is False:
            return False
        self.start(download=choice is True)
        return self.chosen() is not False

    def start(self, *, wait: bool = False, download: bool = True) -> LocalVLMStatus:
        """Prepare and start the local model in the background (no-op while already running). `download=False` stops
        at the first download instead (state off, NOT_DOWNLOADED)."""
        if self.disabled:
            self._set(state="disabled", message="turned off by TWINSTORE_LOCAL_VLM")
            return self.status()
        self.status(check_external=True)
        with self._lock:
            # Stop may have arrived after auto_start read the preference or a button saved Start.
            # Only a subsequent choose(True) may supersede that explicit Stop.
            if self._choice is False:
                return self._status.model_copy()
            busy = self._stopping or (self._thread is not None and self._thread.is_alive())
            ready = self._status.state == "ready" and (self._proc is None or self._proc.poll() is None)
            if download:
                self._may_download = True    # a start already under way may go on to download
            if not busy and not ready:
                self._may_download = download
                self._cancel.clear()
                self._thread = threading.Thread(target=self._run, name="local-vlm", daemon=True)
                self._thread.start()
            thread = self._thread
        if wait and thread is not None:
            thread.join()
        return self.status()

    def stop(self) -> None:
        with self._lock:
            self._cancel.set()
            proc, self._proc = self._proc, None
            if proc is not None:
                self._stopping = True
            if proc is not None or self._status.managed or (self._thread is not None and self._thread.is_alive()):
                self._status = self._status.model_copy(update={
                    "state": "off", "message": "stopped", "managed": False, "api_base": None, "progress": None,
                })
        if proc is not None:
            try:
                _terminate(proc)
            finally:
                with self._lock:
                    self._stopping = False

    # ── pipeline ──

    def busy(self) -> bool:
        """A start (or stop) is still under way."""
        with self._lock:
            return self._stopping or (self._thread is not None and self._thread.is_alive())

    def _check_download(self) -> None:
        self._check_cancelled()
        with self._lock:
            if not self._may_download:
                raise _NeedsDownload

    def _run(self) -> None:
        while True:
            try:
                self._pipeline()
                return
            except _NeedsDownload:
                with self._lock:
                    if self._cancel.is_set():
                        return
                    if not self._may_download:
                        self._status = self._status.model_copy(update={
                            "state": "off", "message": NOT_DOWNLOADED, "progress": None, "downloaded": False})
                        return
                # The user pressed Start meanwhile: go on, with the download.

    def _pipeline(self) -> None:
        try:
            self._check_cancelled()
            self._set(state="preparing", message="Reading this computer's hardware", progress=None)
            hw, plan = self.plan()
            self._check_cancelled()
            self._set(hardware=hw, plan=plan)
            # Someone already serves a model there (by hand, or TwinStore from a crashed run). Only a llama.cpp server
            # that reads images will do: any other program answering on 8081 would take every request and fail it.
            if self._answers(DEFAULT_PORT) and _serves_images(f"http://127.0.0.1:{DEFAULT_PORT}/v1"):
                self._ready(f"http://127.0.0.1:{DEFAULT_PORT}/v1", managed=False, runtime="already running")
                return
            self._check_cancelled()
            try:
                server = self._runtime(hw, plan)
            except _NoGpuBuild:
                # A GPU-sized model on a CPU build would load (so nothing falls back) and crawl.
                logger.warning(f"[local_vlm] no llama.cpp {plan.backend} build for this computer; using the CPU plan")
                plan = downgrade(plan, hw)
                self._set(plan=plan)
                server = self._runtime(hw, plan)
            self._check_cancelled()
            files = [self._download_model(plan.model.repo, f) for f in (plan.model.file, plan.model.mmproj)]
            self._check_cancelled()
            try:
                self._serve(server, files[0], files[1], plan)
            except _NoGpuBuild:
                raise
            except RuntimeError as e:
                self._check_cancelled()
                if plan.backend == "cpu":
                    raise
                logger.warning(f"[local_vlm] {plan.backend} build did not start ({e}); falling back to the CPU")
                plan = downgrade(plan, hw)
                self._set(plan=plan)
                server = self._runtime(hw, plan)
                self._check_cancelled()
                files = [self._download_model(plan.model.repo, f) for f in (plan.model.file, plan.model.mmproj)]
                self._check_cancelled()
                self._serve(server, files[0], files[1], plan)
        except _StartCancelled:
            pass
        except _NeedsDownload:
            raise
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
        self._check_cancelled()
        own = os.environ.get("TWINSTORE_LLAMA_SERVER")
        if own and Path(own).is_file():
            self._set(runtime=own)
            return Path(own)
        target = self.home / "bin" / plan.backend
        marker = target / _COMPLETE
        whole = marker.is_file() or _unpacked_before_marker(target, plan.backend)
        if whole and plan.backend == "cuda" and marker.is_file():
            try:
                recorded = marker.read_text(encoding="utf-8").split()[1:]
            except (OSError, UnicodeError):
                whole = False
            else:
                # Older selectors could mark a Windows server plus Linux CUDA libraries complete.
                if any(name.startswith("llama-") and "-bin-" in name and "-cuda-" in name for name in recorded):
                    whole = len(pick_runtime_assets(recorded, os_name=hw.os, arch=hw.arch, backend="cuda")) == 2
        found = _find_server(target) if whole else None
        if found is not None:
            if plan.backend == "cuda":
                _place_cuda_libraries(target, found)
            self._set(runtime=str(found))
            return found
        self._check_download()
        if target.exists():
            remove_tree(target)        # a build left half-installed
        self._set(state="downloading", message=f"Getting llama.cpp for {plan.backend.upper()}")
        try:
            with self._open(urllib.request.Request(RELEASES_URL, headers={"Accept": "application/vnd.github+json",
                                                                          "User-Agent": "TwinStore"})) as r:
                listed: object = json.loads(r.read().decode())
        except OSError as e:
            # Offline: a llama-server the user installed (brew, winget, a build) is better than none. It comes after
            # TwinStore's own build, since an old one may not take the options TwinStore passes.
            installed = shutil.which("llama-server")
            if installed:
                self._set(runtime=installed)
                return Path(installed)
            raise RuntimeError(
                f"could not reach GitHub to download llama.cpp ({e}). Install llama.cpp (e.g. `brew install llama.cpp`, "
                "`winget install llama.cpp`) so that `llama-server` is on the PATH, or set TWINSTORE_LLAMA_SERVER "
                "to its path, then start the local model again") from e
        releases = [cast(dict[str, object], r) for r in cast(list[object], listed) if isinstance(r, dict)] \
            if isinstance(listed, list) else []
        gpu = hw.best_gpu
        chosen = pick_release(releases, os_name=hw.os, arch=hw.arch, backend=plan.backend, cuda=gpu.cuda if gpu else "")
        if chosen is None:
            raise RuntimeError(
                f"no llama.cpp build for {hw.os}/{hw.arch} in its {len(releases)} latest releases. Install llama.cpp "
                "(e.g. `winget install llama.cpp`, `brew install llama.cpp`) so that `llama-server` is on the PATH, or "
                "set TWINSTORE_LLAMA_SERVER to its path, then start the local model again")
        tag, names, assets = chosen
        if plan.backend in ("cuda", "vulkan") and f"-{plan.backend}-" not in names[0]:
            raise _NoGpuBuild
        target.mkdir(parents=True, exist_ok=True)
        for name in names:
            archive = self._download(assets[name], target / name, label=f"llama.cpp {tag}")
            self._check_cancelled()
            _safe_extract(archive, target)
            try:
                archive.unlink(missing_ok=True)
            except OSError:            # an antivirus still reading it; it goes with the next clean-up
                logger.info(f"[local_vlm] could not remove {archive.name} yet")
        found = _find_server(target)
        if found is None:
            raise RuntimeError("llama-server not found in the downloaded build (an antivirus may have removed it)")
        if plan.backend == "cuda":
            _place_cuda_libraries(target, found)
        if os.name != "nt":
            for exe in found.parent.iterdir():
                if exe.is_file() and not exe.suffix:
                    exe.chmod(exe.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        (target / _COMPLETE).write_text(f"{tag} {' '.join(names)}\n", encoding="utf-8")
        self._set(runtime=f"{tag} {names[0]}")
        return found

    def _download_model(self, repo: str, file: str) -> Path:
        self._check_cancelled()
        path = self.home / "models" / repo.replace("/", "__") / file
        if path.is_file() and path.stat().st_size > 0:
            return path
        return self._download(HF_URL.format(repo=repo, file=file), path, label=file)

    def _download(self, url: str, path: Path, *, label: str) -> Path:
        """Download to `<path>.part`, then move it into place. A `.part` left by a dropped connection, a sleeping laptop
        or a restart is continued where it stopped (HTTP range request) rather than fetched again from zero."""
        self._check_download()
        path.parent.mkdir(parents=True, exist_ok=True)
        part = path.with_name(path.name + ".part")
        have = part.stat().st_size if part.is_file() else 0
        self._set(state="downloading", message=f"Downloading {label}", progress=0.0, downloaded_mb=round(have / 1e6, 1),
                  total_mb=0.0)
        headers = {"User-Agent": "TwinStore"} | ({"Range": f"bytes={have}-"} if have else {})
        keep_part = True
        try:
            try:
                response = self._open(urllib.request.Request(url, headers=headers))
            except urllib.error.HTTPError as exc:
                if exc.code != 416 or not have:
                    raise
                # A complete or stale .part cannot be resumed. Retry once from zero;
                # the next request has no partial file, so a repeated 416 propagates.
                exc.close()
                part.unlink(missing_ok=True)
                return self._download(url, path, label=label)
            range_end: int | None = None
            with response as r:
                partial = getattr(r, "status", 200) == 206
                resumed = have > 0 and partial
                done = have if resumed else 0
                length = getattr(r, "headers", {}).get("Content-Length")
                total = done + int(length) if length is not None else None
                if partial:
                    content_range = getattr(r, "headers", {}).get("Content-Range", "")
                    match = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)", content_range)
                    if match is None:
                        keep_part = False
                        raise RuntimeError(f"Download of {label} has no verifiable byte range; retry from the beginning")
                    start, end, resource_size = (int(value) for value in match.groups())
                    if (start != have or end < start or end >= resource_size
                            or (total is not None and total != end + 1)):
                        keep_part = False
                        raise RuntimeError(f"Download of {label} returned an inconsistent byte range; retry from the beginning")
                    range_end, total = end + 1, resource_size
                last = 0.0
                with part.open("ab" if resumed else "wb") as out:
                    while chunk := r.read(1 << 20):
                        self._check_cancelled()
                        out.write(chunk)
                        done += len(chunk)
                        if time.monotonic() - last > 0.5:
                            last = time.monotonic()
                            self._set(progress=min(done / total, 1.0) if total else None,
                                      downloaded_mb=round(done / 1e6, 1), total_mb=round(total / 1e6, 1) if total else 0.0)
            self._check_cancelled()
            if range_end is not None and done > range_end:
                keep_part = False
                raise RuntimeError(f"Download of {label} exceeded its declared byte range; retry from the beginning")
            if done == 0 or (total is not None and done != total):
                keep_part = total is not None and done < total     # a short read can go on next time
                raise RuntimeError(f"Download of {label} is incomplete: received {done} bytes, expected {total if total is not None else 'a nonempty file'}")
            replace_file(part, path)
        except _StartCancelled:
            keep_part = False                                         # the user stopped it: start clean next time
            raise
        finally:
            if not keep_part or path.is_file():
                part.unlink(missing_ok=True)
        self._set(progress=1.0, downloaded_mb=round(done / 1e6, 1))
        return path

    def _serve(self, server: Path, model: Path, mmproj: Path, plan: LocalVLMPlan) -> None:
        self._check_cancelled()
        port = DEFAULT_PORT if _port_free(DEFAULT_PORT) else _free_port()
        self._set(state="starting", message=f"Starting {plan.model.label} on {plan.device}", progress=None)
        cmd = [str(server), "-m", str(model), "--mmproj", str(mmproj), "--host", "127.0.0.1", "--port", str(port),
               "-c", str(plan.context), "-np", str(plan.parallel), "-ngl", str(plan.gpu_layers), "-t", str(plan.threads),
               "--reasoning", "off", "--image-max-tokens", "512", "--cache-ram", "256", "--no-webui", "-a", "local-model"]
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        with self._lock:
            self._check_cancelled()
            with (self.home / "server.log").open("ab") as log:
                proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                        creationflags=flags)
            _end_with_this_process(proc)
            self._proc = proc
        deadline = time.monotonic() + 600
        while time.monotonic() < deadline:
            self._check_cancelled()
            if proc.poll() is not None:
                raise RuntimeError(f"llama-server exited with code {proc.returncode} (see {self.home / 'server.log'})")
            if self._answers(port):
                self._ready(f"http://127.0.0.1:{port}/v1", managed=True, runtime=self._status.runtime)
                return
            self._cancel.wait(1.0)
        _terminate(proc)
        with self._lock:
            if self._proc is proc:
                self._proc = None
        raise RuntimeError("the local model did not load within 10 minutes")

    def _ready(self, api_base: str, *, managed: bool, runtime: str) -> None:
        from . import providers  # late import: providers imports nothing from here

        plan = self._status.plan
        label = f"{plan.model.label} on {plan.device}" if plan and managed else "the llama.cpp server on this computer"
        slots = plan.parallel if plan and managed else _server_slots(api_base)
        with self._lock:
            self._check_cancelled()
            providers.use_local_server(api_base)
            self._status = self._status.model_copy(update={
                "state": "ready", "message": f"Ready: {label}", "api_base": api_base, "managed": managed,
                "runtime": runtime, "progress": None, "slots": slots,
            })
        logger.info(f"[local_vlm] ready at {api_base} ({label})")


if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    class _BasicLimits(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                    ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD), ("SchedulingClass", wintypes.DWORD)]

    class _IoCounters(ctypes.Structure):
        _fields_ = [(name, ctypes.c_uint64) for name in ("ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                                                         "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

    class _ExtendedLimits(ctypes.Structure):
        _fields_ = [("BasicLimitInformation", _BasicLimits), ("IoInfo", _IoCounters),
                    ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]

    _KERNEL32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _KERNEL32.CreateJobObjectW.restype = wintypes.HANDLE
    _KERNEL32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    _KERNEL32.SetInformationJobObject.restype = wintypes.BOOL
    _KERNEL32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    _KERNEL32.AssignProcessToJobObject.restype = wintypes.BOOL
    _KERNEL32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    _JOB: list[int] = []

    def _end_with_this_process(proc: subprocess.Popen[bytes]) -> None:
        """Windows does not end a child with its parent: when this server is killed outright (its console window
        closed, Task Manager) the local model server would keep its memory and port. A job object that ends its
        processes when its last handle closes, held by this process, ties the two together."""
        try:
            if not _JOB:
                job = _KERNEL32.CreateJobObjectW(None, None)
                limits = _ExtendedLimits()
                limits.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
                if not job or not _KERNEL32.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
                    return
                _JOB.append(job)
            if not _KERNEL32.AssignProcessToJobObject(_JOB[0], int(proc._handle)):  # type: ignore[attr-defined]  # Popen's process handle on Windows
                logger.info(f"[local_vlm] could not tie llama-server to this process (error {ctypes.get_last_error()})")
        except (OSError, AttributeError, ValueError) as e:
            logger.info(f"[local_vlm] could not tie llama-server to this process: {e}")
else:
    def _end_with_this_process(proc: subprocess.Popen[bytes]) -> None:
        """Elsewhere the app launcher stops the server's whole process group, and a closed terminal hangs it up."""


def server_answers(api_base: str) -> bool:
    """Whether a local model API answers without reporting that it is loading or unavailable."""
    try:
        base = urlsplit(api_base)
        if base.scheme not in ("http", "https") or base.hostname is None:
            return False
    except ValueError:
        return False
    path = base.path.rstrip("/")
    root = path.removesuffix("/v1")
    # llama.cpp/vLLM expose health; LM Studio exposes models; Ollama exposes tags.
    probes = ((root + "/health", None), (path + "/models", "data"), (root + "/api/tags", "models"))
    for probe, listing in probes:
        url = base._replace(path=probe, fragment="").geturl()
        try:
            with _DIRECT.open(url, timeout=2) as response:
                if getattr(response, "status", 200) != 200:
                    return False
                raw = response.read()
                # vLLM uses an empty 200; other servers return a short health
                # marker. A web app's HTML catch-all is not model readiness.
                if listing is None and raw.strip().lower() in (b"", b"ok", b"healthy"):
                    return True
                data: object = json.loads(raw)
        except urllib.error.HTTPError as exc:
            code = exc.code
            exc.close()
            if code in (401, 403):
                return True  # The inference request checks the configured credential.
            if code not in (404, 405, 501):
                return False  # A loading 503 must not become ready just because models can be listed.
            continue
        except json.JSONDecodeError:
            continue
        except (OSError, ValueError):
            return False
        if listing is None:
            status = cast(dict[str, object], data).get("status") if isinstance(data, dict) else data
            if isinstance(status, str) and status.strip().lower() in {"ok", "healthy", "ready", "no slot available"}:
                return True
        elif isinstance(data, dict) and isinstance(cast(dict[str, object], data).get(listing), list):
            return True
    return False


def _props(api_base: str) -> dict[str, object] | None:
    root = api_base.removesuffix("/").removesuffix("/v1")
    try:
        with _DIRECT.open(f"{root}/props", timeout=3) as r:
            data: object = json.loads(r.read().decode("utf-8", "replace"))
    except (OSError, ValueError):
        return None
    return cast(dict[str, object], data) if isinstance(data, dict) else None


def _serves_images(api_base: str) -> bool:
    """A llama.cpp server (it has /props) whose model reads images; a server that does not say counts as one."""
    props = _props(api_base)
    if props is None or "total_slots" not in props:
        return False
    modalities = props.get("modalities")
    return not isinstance(modalities, dict) or bool(cast(dict[str, object], modalities).get("vision", True))


def _server_slots(api_base: str) -> int:
    """How many requests a llama.cpp server already running here answers at once (its /props), 1 when it does not
    say: asking it for more only makes requests queue there, where their time-out runs."""
    props = _props(api_base)
    slots = props.get("total_slots") if props is not None else None
    return slots if isinstance(slots, int) and slots > 0 else 1


def _terminate(proc: subprocess.Popen[bytes]) -> None:
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


_DIRECT = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _urlopen(req: urllib.request.Request) -> IO[bytes]:
    return cast(IO[bytes], urllib.request.urlopen(req, timeout=60))


def _port_free(port: int) -> bool:
    """Nothing answers on the port and it can be listened on: Windows reserves port ranges for Hyper-V, WSL and
    Docker that refuse connections and listening alike."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if s.connect_ex(("127.0.0.1", port)) == 0:
            return False
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", port))
    except OSError:
        return False
    return True


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
