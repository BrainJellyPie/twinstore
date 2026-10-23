"""Resolve this project's product photos for model input without HTTP round trips."""
import re
from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from PIL import Image
from pydantic import BaseModel, Field, TypeAdapter

from store_emulator.application.errors import AppError
from store_emulator.application.library_photos import photo_file
from store_emulator.application.shelf_lab import package_directory, package_path
from store_emulator.application.storage.images import image_read_transaction, layout_image_url, load_manifest, resolve_image
from store_emulator.application.storage.io import write_json
from store_emulator.domain.rack import SlotItem
from store_emulator.domain.types import RESOURCE_ID_PATTERN
from store_emulator.engine.perception.product_images import ProductImageLoader, bundled_product_image, file_product_image


def project_image_loader(pid: str) -> ProductImageLoader:
    if re.fullmatch(RESOURCE_ID_PATTERN, pid) is None:
        raise ValueError("Invalid project ID")
    manifest = load_manifest(pid)
    prefix = f"/api/projects/{pid}/"
    package_root = package_directory(pid).resolve()

    @lru_cache(maxsize=128)
    def load(url: str) -> Image.Image | None:
        try:
            if url.startswith("/api/catalog-images/"):
                return bundled_product_image(url)
            if url.startswith("file://"):
                path = Path(unquote(url.removeprefix("file://"))).resolve()
                if path.parent == package_root and path.suffix.lower() == ".png":
                    return file_product_image(path)
                return None
            parsed = urlsplit(url)
            if parsed.scheme or parsed.netloc or parsed.fragment or not parsed.path.startswith(prefix):
                return None
            relative = parsed.path.removeprefix(prefix)
            if relative == "images":
                query = parse_qs(parsed.query, keep_blank_values=True)
                skus = query.get("sku", [])
                if len(skus) != 1 or not skus[0]:
                    return None
                found = resolve_image(pid, skus[0])
                return file_product_image(found[0]) if found else None
            if parsed.query:
                return None
            if re.fullmatch(r"product-photo-files/[0-9a-f]{64}", relative):
                return file_product_image(photo_file(pid, relative.rsplit("/", 1)[1]))
            if relative.startswith("lab/packages/"):
                return file_product_image(package_path(pid, relative.removeprefix("lab/packages/")))
        except (AppError, OSError, ValueError):
            return None
        return None

    def resolve(item: SlotItem) -> Image.Image | None:
        # Explicit experiment art and reviewed immutable photos keep their intended identity.
        url = item.image_url if item.image_url and item.image_url.startswith("file://") else layout_image_url(pid, item.sku, item.image_url, manifest)
        return load(url) if url else None

    return resolve


def snapshot_project_images(pid: str, items: Iterable[SlotItem], folder: Path) -> ProductImageLoader:
    """Freeze resolved art (including absent art) under the caller's project tree guard.

    Keep decoded images in a bounded cache, with copies on disk so eviction cannot reload changed source art.
    SKU writers use their own lock; the outer project guard also excludes package and project deletion.
    """
    paths: dict[tuple[str, str | None], Path | None] = {}
    with image_read_transaction(pid):
        source = project_image_loader(pid)
        folder.mkdir(parents=True, exist_ok=True)
        for item in items:
            key = item.sku, item.image_url
            if key in paths:
                continue
            picture = source(item)
            path = folder / f"{len(paths)}.png" if picture is not None else None
            if picture is not None and path is not None:
                picture.save(path, format="PNG")
            paths[key] = path
        write_json(folder / "manifest.json", [
            {"sku": sku, "image_url": url, "file": path.name if path else None}
            for (sku, url), path in paths.items()
        ])
    return _snapshot_loader(paths)


class _SnapshotImage(BaseModel):
    sku: str
    image_url: str | None
    file: str | None = Field(pattern=r"^[0-9]+\.png$")


def snapshot_image_loader(folder: Path) -> ProductImageLoader:
    """Reopen accepted artwork from its manifest without consulting mutable project art."""
    entries = TypeAdapter(list[_SnapshotImage]).validate_json((folder / "manifest.json").read_bytes())
    return _snapshot_loader({(entry.sku, entry.image_url): folder / entry.file if entry.file else None for entry in entries})


def _snapshot_loader(paths: dict[tuple[str, str | None], Path | None]) -> ProductImageLoader:
    @lru_cache(maxsize=128)
    def load(path: Path) -> Image.Image | None:
        return file_product_image(path)

    def resolve(item: SlotItem) -> Image.Image | None:
        path = paths.get((item.sku, item.image_url))
        return load(path) if path is not None else None

    return resolve
