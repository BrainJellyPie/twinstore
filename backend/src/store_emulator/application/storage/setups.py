import logging
from pathlib import Path
from typing import Any, cast

from store_emulator.application.storage.io import (
    DATA_DIR, read_json, write_json, now_iso, generate_setup_id,
)

logger = logging.getLogger(__name__)


def setup_dir(project_id: str) -> Path:
    return Path(DATA_DIR) / project_id / "setups"


def setup_path(project_id: str, setup_id: str) -> Path:
    return setup_dir(project_id) / f"{setup_id}.json"


def state_path(project_id: str) -> Path:
    return Path(DATA_DIR) / project_id / "state.json"


def personas_path(project_id: str) -> Path:
    return Path(DATA_DIR) / project_id / "personas.json"


def metadata_path(project_id: str) -> Path:
    return Path(DATA_DIR) / project_id / "metadata.json"


def delete_setup(project_id: str, setup_id: str) -> None:
    path = setup_path(project_id, setup_id)
    if path.exists():
        path.unlink()


def find_descendants(project_id: str, setup_id: str) -> list[str]:
    """Return every descendant ID of setup_id (excluding itself)."""
    all_setups = list_setups(project_id)
    children_map: dict[str, list[str]] = {}
    for s in all_setups:
        pid = s.get("parentId")
        if pid:
            children_map.setdefault(pid, []).append(s["id"])

    result: list[str] = []
    seen = {setup_id}
    queue = list(children_map.get(setup_id, []))
    while queue:
        sid = queue.pop(0)
        if sid in seen:
            continue
        seen.add(sid)
        result.append(sid)
        queue.extend(children_map.get(sid, []))
    return result


def read_setup(project_id: str, setup_id: str) -> dict[str, Any]:
    path = setup_path(project_id, setup_id)
    if not path.exists():
        raise FileNotFoundError(f"Setup not found: {setup_id}")
    data: dict[str, object] = read_json(path)
    store, generation = data.get("store"), data.get("generation")
    # Earlier template layouts recorded their currency only in generation provenance.
    if isinstance(store, dict) and isinstance(generation, dict):
        store_fields = cast(dict[str, object], store)
        currency = cast(dict[str, object], generation).get("currency")
        if store_fields.get("currency") is None and isinstance(currency, str) and currency in {"USD", "KRW", "JPY"}:
            store_fields["currency"] = currency
    return data


def write_setup(project_id: str, setup_id: str, data: dict[str, Any]) -> None:
    data["updated_at"] = now_iso()
    write_json(setup_path(project_id, setup_id), data)


def list_setups(project_id: str, *, include_store: bool = False) -> list[dict[str, Any]]:
    """Return setups sorted by updated_at, omitting stores unless requested for readiness."""
    d = setup_dir(project_id)
    if not d.exists():
        return []
    results: list[dict[str, Any]] = []
    for f in d.iterdir():
        if not f.suffix == ".json":
            continue
        data = read_json(f)
        summary = {k: v for k, v in data.items() if include_store or k != "store"}
        results.append(summary)
    results.sort(key=lambda s: str(s.get("updated_at", "")), reverse=True)
    return results


def read_state(project_id: str) -> dict[str, Any]:
    """Read state.json; returns ``{"activeSetupId": None}`` when absent."""
    path = state_path(project_id)
    if path.exists():
        return read_json(path)
    return {"activeSetupId": None}


def write_state(project_id: str, data: dict[str, Any]) -> None:
    write_json(state_path(project_id), data)


def new_setup_data(
    name: str,
    parent_id: str | None,
    store: dict[str, Any] | None = None,
    memo: str = "",
) -> dict[str, Any]:
    """Build a draft setup skeleton dict. Single source of truth — every new-setup path uses this."""
    now = now_iso()
    return {
        "id": generate_setup_id(),
        "name": name,
        "status": "draft",
        "parentId": parent_id,
        "store": store,
        "runId": None,
        "memo": memo,
        "created_at": now,
        "updated_at": now,
    }


def create_initial_setup(
    project_id: str,
    store: dict[str, Any] | None = None,
) -> dict[str, Any]:
    setup_data = new_setup_data("layout 1", parent_id=None, store=store)
    setup_dir(project_id).mkdir(parents=True, exist_ok=True)
    write_json(setup_path(project_id, setup_data["id"]), setup_data)
    return setup_data


def recover_running_setups() -> int:
    """Server-startup recovery: revert every running setup back to draft. Returns count."""
    recovered = 0
    data_root = Path(DATA_DIR)
    if not data_root.exists():
        return 0
    for proj_dir in data_root.iterdir():
        if not proj_dir.is_dir() or not proj_dir.name.startswith("proj_"):
            continue
        setups = proj_dir / "setups"
        if not setups.exists():
            continue
        for sf in setups.iterdir():
            if sf.suffix != ".json":
                continue
            data = read_json(sf)
            if data.get("status") == "running":
                data["status"] = "draft"
                data["updated_at"] = now_iso()
                write_json(sf, data)
                recovered += 1
                logger.info(f"[recovery] {proj_dir.name}/{sf.stem}: running → draft")
    return recovered
