"""Photos of a layout's shelf faces from the 3D store, for vision runs with the "photo_chart" shelf view.

The server says which faces a layout has and under which key each picture is stored; the browser renders
the faces still missing and uploads them; a run points the vision engine at the project's picture folder.
Pictures are kept per project and shared by layouts with identical racks.
"""

import base64
import binascii
import shutil
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from filelock import FileLock, Timeout

from store_emulator.application.currencies import simulation_currency
from store_emulator.application.errors import AppError
from store_emulator.application.storage.io import DATA_DIR, write_json
from store_emulator.application.setups import setup_lock_path, setup_tree_transaction
from store_emulator.domain.store import Store
from store_emulator.domain.types import Face
from store_emulator.engine.perception.shelf_photo import (
    face_key,
    has_shelf_photo,
    load_shelf_photo,
    save_shelf_photo,
    stocked_faces,
)


class ShelfFace(BaseModel):
    rack_id: str
    rack_name: str
    face: Face
    key: str
    ready: bool


class ShelfViewStatus(BaseModel):
    currency: str
    faces: list[ShelfFace]
    store: dict[str, Any]


class ShelfViewUpload(BaseModel):
    rack_id: str = Field(min_length=1, max_length=120)
    face: Face
    image: str = Field(min_length=32, max_length=6_000_000, description="data:image/jpeg;base64,… or PNG")
    # The picture's box (x1, y1, x2, y2 in pixels) of each product, by "face:level:block:index".
    boxes: dict[str, list[tuple[float, float, float, float]]] = Field(default_factory=dict, max_length=400)


def views_dir(pid: str) -> Path:
    return (Path(DATA_DIR) / pid / "shelf_views").resolve()


def _setup_store(pid: str, sid: str, default_currency: str) -> tuple[Store, str]:
    from store_emulator.application.setups import get_setup

    setup = get_setup(pid, sid)
    if not setup.get("store"):
        raise AppError("this layout has no store yet.", 409)
    store = Store.model_validate(setup["store"])
    currency = simulation_currency(pid, store, default_currency)
    return store, currency


def shelf_view_status(pid: str, sid: str, default_currency: str = "USD") -> ShelfViewStatus:
    store, currency = _setup_store(pid, sid, default_currency)
    directory = views_dir(pid)
    faces: list[ShelfFace] = []
    for rack in store.product_racks:
        for face in stocked_faces(rack):
            key = face_key(rack, face, currency)
            faces.append(ShelfFace(rack_id=rack.id, rack_name=rack.rack_name, face=face, key=key,
                                   ready=has_shelf_photo(directory, key)))
    return ShelfViewStatus(currency=currency, faces=faces, store=store.model_dump(mode="json"))


def _decode(data_url: str) -> bytes:
    head, _, body = data_url.partition(",")
    if not body or head not in ("data:image/jpeg;base64", "data:image/png;base64"):
        raise AppError("the picture must be a JPEG or PNG data URL.", 422)
    try:
        return base64.b64decode(body, validate=True)
    except (binascii.Error, ValueError) as e:
        raise AppError("the picture is not valid base64.", 422) from e


def save_shelf_view(pid: str, sid: str, key: str, upload: ShelfViewUpload, default_currency: str = "USD") -> ShelfFace:
    """Stores one face picture. 409 when the layout changed since the key was handed out."""
    try:
        with setup_tree_transaction(pid, [sid]), FileLock(setup_lock_path(pid, sid), timeout=10):
            return _save_shelf_view(pid, sid, key, upload, default_currency)
    except Timeout:
        raise AppError("another request is modifying this setup. Please retry shortly.", 503) from None


def _save_shelf_view(pid: str, sid: str, key: str, upload: ShelfViewUpload, default_currency: str) -> ShelfFace:
    store, currency = _setup_store(pid, sid, default_currency)
    rack = next((r for r in store.product_racks if r.id == upload.rack_id), None)
    if rack is None or upload.face not in stocked_faces(rack):
        raise AppError("this shelf face is not in the layout any more; render the shelves again.", 409)
    if face_key(rack, upload.face, currency) != key:
        raise AppError("this shelf changed since it was rendered; render the shelves again.", 409)
    boxes = {ref: list(items) for ref, items in upload.boxes.items()}
    try:
        save_shelf_photo(views_dir(pid), key, _decode(upload.image), boxes)
    except ValueError as e:
        raise AppError(str(e), 422) from e
    return ShelfFace(rack_id=rack.id, rack_name=rack.rack_name, face=upload.face, key=key, ready=True)


def snapshot_shelf_views(pid: str, store: Store, currency: str, folder: Path) -> None:
    """Copy matching photo/box pairs under the caller's tree guard; missing photos stay absent."""
    directory = views_dir(pid)
    folder.mkdir(parents=True, exist_ok=True)
    keys: list[str] = []
    for rack in store.product_racks:
        for face in stocked_faces(rack):
            key = face_key(rack, face, currency)
            if has_shelf_photo(directory, key):
                for extension in ("jpg", "json"):
                    shutil.copyfile(directory / f"{key}.{extension}", folder / f"{key}.{extension}")
                keys.append(key)
    write_json(folder / "manifest.json", {"keys": keys})
    load_shelf_photo.cache_clear()
