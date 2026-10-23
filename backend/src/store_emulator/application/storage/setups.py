import logging
from pathlib import Path
from typing import Any, cast

from store_emulator.application.storage.io import (
    DATA_DIR, DamagedFile, read_json, write_json, now_iso, generate_setup_id,
)

logger = logging.getLogger(__name__)


def setup_dir(project_id: str) -> Path:
    return Path(DATA_DIR) / project_id / "setups"


def setup_path(project_id: str, setup_id: str) -> Path:
    return setup_dir(project_id) / f"{setup_id}.json"


def deleted_setup_path(project_id: str, setup_id: str) -> Path:
    """Deletion marker for replay-safe saves with deterministic setup IDs."""
    return setup_dir(project_id) / ".deleted" / f"{setup_id}.json"


def state_path(project_id: str) -> Path:
    return Path(DATA_DIR) / project_id / "state.json"


def personas_path(project_id: str) -> Path:
    return Path(DATA_DIR) / project_id / "personas.json"


def metadata_path(project_id: str) -> Path:
    return Path(DATA_DIR) / project_id / "metadata.json"


def delete_setup(project_id: str, setup_id: str) -> None:
    path = setup_path(project_id, setup_id)
    if path.exists():
        write_json(deleted_setup_path(project_id, setup_id), {"deleted_at": now_iso()})
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
    raw: object = read_json(path)
    if not isinstance(raw, dict):
        raise DamagedFile(path, "expected a JSON object")
    data = cast(dict[str, object], raw)
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
        try:
            raw: object = read_json(f)
            if not isinstance(raw, dict):
                raise DamagedFile(f, "expected a JSON object")
            data = cast(dict[str, object], raw)
        except (OSError, ValueError) as e:   # a damaged layout file must not hide the others
            logger.warning(f"[setups] skipping {f.name} of {project_id}: unreadable ({type(e).__name__}: {e})")
            continue
        summary = {k: v for k, v in data.items() if include_store or k != "store"}
        results.append(summary)
    results.sort(key=lambda s: str(s.get("updated_at", "")), reverse=True)
    return results


def read_state(project_id: str) -> dict[str, Any]:
    """Read state.json; returns ``{"activeSetupId": None}`` when absent or unreadable (it only remembers the layout
    last open: a damaged one must not keep the store from opening)."""
    path = state_path(project_id)
    if path.exists():
        try:
            raw: object = read_json(path)
        except ValueError as e:
            logger.warning(f"[setups] ignoring the open layout of {project_id}: {e}")
            raw = None
        if isinstance(raw, dict):
            return cast(dict[str, Any], raw)
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
            try:
                raw: object = read_json(sf)
                if not isinstance(raw, dict):
                    raise ValueError("setup must be an object")
                data = cast(dict[str, object], raw)
                if data.get("status") == "running":
                    # A final run that completed just before the restart locks its layout, as it would have.
                    finished = [run for run, setup in final_runs(proj_dir.name) if setup == sf.stem]
                    if finished:
                        data["status"], data["runId"] = "locked", finished[-1]
                    else:
                        data["status"] = "draft"
                    data["updated_at"] = now_iso()
                    write_json(sf, data)
                    recovered += 1
                    logger.info(f"[recovery] {proj_dir.name}/{sf.stem}: running → {data['status']}")
            except (OSError, ValueError) as exc:
                logger.warning("Could not recover setup %s: %s", sf, exc)
    return recovered


def final_runs(project_id: str) -> list[tuple[str, str]]:
    """(run id, layout id) of the project's completed final (not preview) runs, oldest first. They fix the
    customers: regenerated ones would reuse ids (M1001…) and pair with different people in comparisons."""
    runs = Path(DATA_DIR) / project_id / "runs"
    found: list[tuple[str, str, str]] = []
    if not runs.is_dir():
        return []
    for run in runs.iterdir():
        try:
            raw: object = read_json(run / "status.json")
        except (OSError, ValueError):
            continue
        if not isinstance(raw, dict):
            continue
        status = cast(dict[str, object], raw)
        if status.get("status") == "completed" and status.get("preview") is not True:
            when = status.get("finished_at") or status.get("created_at") or ""
            found.append((str(when), run.name, str(status.get("setup_id") or "")))
    return [(run, setup) for _, run, setup in sorted(found)]


def has_run_history(project_id: str) -> bool:
    """A layout finalized by a run, or a final run on disk (its layout may have been deleted since)."""
    return any(s.get("runId") for s in list_setups(project_id)) or bool(final_runs(project_id))
