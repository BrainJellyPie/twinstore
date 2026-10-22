"""Validated product-layout snapshot shared by explicit editing and starter filling."""
import hashlib
import json
import re
from store_emulator.application.currencies import project_currency
from store_emulator.application.errors import AppError
from store_emulator.application.storage.generations import find_active_generation
from store_emulator.application.storage.setups import metadata_path, read_setup
from store_emulator.domain.product_edits import MAX_PRICE
from store_emulator.domain.store import Store


def check_product_layout(pid: str, sid: str) -> None:
    if any(not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value) for value in (pid, sid)):
        raise AppError("Invalid project or layout identifier", 422)
    if not metadata_path(pid).exists():
        raise AppError("Project not found", 404)


def read_product_source(pid: str, sid: str) -> tuple[Store, str]:
    check_product_layout(pid, sid)
    try:
        source = read_setup(pid, sid)
    except FileNotFoundError as exc:
        raise AppError("Source layout no longer exists", 404) from exc
    except (ValueError, AttributeError) as exc:
        raise AppError("Stored layout data is unreadable. Restore a valid copy before editing", 409) from exc
    if find_active_generation(pid, sid, "layout"):
        raise AppError("Layout generation is in progress; reload when it finishes", 409)
    if not source.get("store"):
        raise AppError("Create a layout before editing products", 409)
    try:
        store = Store.model_validate(source["store"])
        store.currency = store.currency or project_currency(pid, "USD")
        payload = json.dumps(store.model_dump(mode="json"), sort_keys=True, ensure_ascii=False, allow_nan=False)
    except ValueError as exc:
        raise AppError("The stored layout is invalid; repair it before editing products", 409) from exc
    items = [item for rack in store.racks for slot in rack.slots for item in slot.items]
    if len(items) > 50_000 or len({item.sku for item in items}) > 5_000:
        raise AppError("Edit layouts with at most 5,000 SKUs and 50,000 placements", 413)
    if any(item.price > MAX_PRICE for item in items):
        raise AppError("A stored price exceeds the safe integer limit; correct it first", 409)
    return store, hashlib.sha256(payload.encode()).hexdigest()

