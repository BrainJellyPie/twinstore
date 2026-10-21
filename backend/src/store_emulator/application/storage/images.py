"""Per-project SKU image storage; sku → file mapping is kept in manifest.json."""

from __future__ import annotations

import hashlib
import io
import json
import re
import shutil
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Final
from urllib.parse import quote

from PIL import Image, UnidentifiedImageError

from store_emulator.domain.types import RESOURCE_ID_PATTERN

from .io import DATA_DIR, read_json, write_json
from .setups import metadata_path


MAX_IMAGE_BYTES: Final[int] = 2 * 1024 * 1024  # 2MB
_ALLOWED_FORMATS: Final[dict[str, tuple[str, str]]] = {
    # PIL format string -> (mime, file extension)
    "PNG": ("image/png", "png"),
    "JPEG": ("image/jpeg", "jpg"),
    "WEBP": ("image/webp", "webp"),
}
_SAFE_PID: Final[re.Pattern[str]] = re.compile(RESOURCE_ID_PATTERN)

# Per-project lock that serializes manifest writes. Assumes a single process
# (single uvicorn worker). Prevents lost-update on concurrent save_image calls
# for the same project_id.
_PROJECT_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_MUTEX: Final[threading.Lock] = threading.Lock()


def _project_lock(project_id: str) -> threading.Lock:
    with _LOCKS_MUTEX:
        lock = _PROJECT_LOCKS.get(project_id)
        if lock is None:
            lock = threading.Lock()
            _PROJECT_LOCKS[project_id] = lock
        return lock


class ImageStorageError(Exception):
    pass


class ImageTooLargeError(ImageStorageError):
    pass


class UnsupportedImageFormatError(ImageStorageError):
    pass


@dataclass(frozen=True)
class ImageEntry:
    sku: str
    path: str
    mime: str
    ext: str
    version: str


def _project_dir(project_id: str) -> Path:
    if not _SAFE_PID.fullmatch(project_id):
        raise ValueError(f"unsafe project_id: {project_id}")
    return Path(DATA_DIR) / "images" / project_id


def _manifest_path(project_id: str) -> Path:
    return _project_dir(project_id) / "manifest.json"


def _sku_hash(sku: str) -> str:
    return hashlib.sha256(sku.encode("utf-8")).hexdigest()[:16]


def load_manifest(project_id: str) -> dict[str, dict[str, str]]:
    p = _manifest_path(project_id)
    if not p.exists():
        return {}
    # read_json -> Any (JSON parsing boundary); coerce defensively.
    try:
        data = read_json(p)  # type: ignore[reportAny]
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    result: dict[str, dict[str, str]] = {}
    for k, v in data.items():  # type: ignore[reportUnknownVariableType]
        if not isinstance(k, str) or not isinstance(v, dict):
            continue
        entry: dict[str, str] = {}
        for ek, ev in v.items():  # type: ignore[reportUnknownVariableType]
            if isinstance(ek, str) and isinstance(ev, str):
                entry[ek] = ev
        result[k] = entry
    return result


def _save_manifest(project_id: str, manifest: dict[str, dict[str, str]]) -> None:
    write_json(_manifest_path(project_id), manifest)


def save_image(
    project_id: str,
    sku: str,
    data: bytes,
    filename: str,
) -> ImageEntry:
    if len(data) > MAX_IMAGE_BYTES:
        raise ImageTooLargeError(
            f"image too large (max {MAX_IMAGE_BYTES // (1024 * 1024)}MB): {filename}",
        )
    try:
        with Image.open(io.BytesIO(data)) as img:
            fmt = (img.format or "").upper()
            if fmt not in _ALLOWED_FORMATS:
                raise UnsupportedImageFormatError(
                    f"unsupported image format ({fmt}): {filename}",
                )
            img.load()
    except Image.DecompressionBombError as e:
        raise ImageTooLargeError("Image dimensions are too large; reduce the resolution and try again.") from e
    except (UnidentifiedImageError, OSError, ValueError) as e:
        raise UnsupportedImageFormatError(f"failed to identify image format: {filename}") from e
    mime, ext = _ALLOWED_FORMATS[fmt]

    # Serializes manifest read/modify/write within a project and avoids
    # tmp-file collisions for the same SKU.
    with _project_lock(project_id):
        pdir = _project_dir(project_id)
        if not metadata_path(project_id).is_file():
            raise FileNotFoundError(f"Project not found: {project_id}")
        pdir.mkdir(parents=True, exist_ok=True)
        fname = f"{_sku_hash(sku)}.{ext}"
        target = pdir / fname
        tmp = target.with_suffix(target.suffix + f".tmp-{uuid.uuid4().hex[:8]}")
        tmp.write_bytes(data)
        tmp.replace(target)

        version = hashlib.sha256(data).hexdigest()[:8]
        manifest = load_manifest(project_id)
        manifest[sku] = {"path": str(target), "mime": mime, "ext": ext, "version": version}
        _save_manifest(project_id, manifest)

    return ImageEntry(sku=sku, path=str(target), mime=mime, ext=ext, version=version)


def delete_project_images(project_id: str) -> None:
    """Finish any in-flight upload before removing a deleted project's photos."""
    with _project_lock(project_id):
        pdir = _project_dir(project_id)
        if pdir.exists():
            shutil.rmtree(pdir)


def resolve_image(project_id: str, sku: str) -> tuple[Path, str] | None:
    manifest = load_manifest(project_id)
    entry = manifest.get(sku)
    if entry is None:
        return None
    path_str = entry.get("path")
    mime = entry.get("mime")
    if not isinstance(path_str, str) or not isinstance(mime, str):
        return None
    p = Path(path_str).resolve()
    pdir = _project_dir(project_id).resolve()
    try:
        p.relative_to(pdir)
    except ValueError:
        return None
    if not p.is_file():
        return None
    return p, mime


def image_url_for(
    project_id: str,
    sku: str,
    manifest: dict[str, dict[str, str]] | None = None,
) -> str | None:
    if manifest is None:
        manifest = load_manifest(project_id)
    entry = manifest.get(sku)
    if entry is None:
        return None
    version = entry.get("version", "")
    suffix = f"?v={version}" if version else ""
    encoded_sku = quote(sku, safe="")
    return f"/api/projects/{project_id}/images/{encoded_sku}{suffix}"
