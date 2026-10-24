import logging
import math
import uuid
from pathlib import Path
from typing import Any, Literal, cast

from store_emulator.engine.files import remove_tree
from store_emulator.domain.config import SimulationConfig
from store_emulator.domain.store import DaySchedule, Store, validate_weekly_schedule
from store_emulator.domain.layout_options import TemplateLayoutRequest
from store_emulator.application.template_layouts import prepare_template_layout
from store_emulator.application.template_assortment import select_initial_assortment
from store_emulator.application.errors import AppError
from store_emulator.application.workbooks import WorkbookLimitError
from store_emulator.application.customer_csv import CustomerCsvError, CustomerCsvLimitError, validate_customer_csv
from store_emulator.application.supplemental import read_customer_workbook
from store_emulator.application.setups import project_layout_transaction, setup_tree_transaction
from store_emulator.application.generation_async import start_persona_generation
from store_emulator.application.storage.generations import find_active_generation
from store_emulator.application.storage.images import delete_project_images
from store_emulator.application.storage.io import DATA_DIR, DamagedFile, write_json, read_json, now_iso
from store_emulator.application.storage.setups import (
    metadata_path, personas_path,
    read_setup, list_setups, create_initial_setup,
    read_state, write_state, setup_path, final_runs, has_run_history,
)


_data = Path(DATA_DIR)
logger = logging.getLogger(__name__)


_DRAWN = {"shelf", "fridge", "counter", "table"}
MAX_FOOTPRINT_RACKS = 160


def _footprint(store: object) -> dict[str, object] | None:
    """The active layout as rectangles for the gallery tile: grid size and [x, y, w, h, type] per fixture."""
    def integer(value: object) -> int | None:
        if isinstance(value, bool) or not isinstance(value, int | float):
            return None
        try:
            return int(value) if math.isfinite(value) and int(value) == value else None
        except OverflowError:
            return None

    if not isinstance(store, dict):
        return None
    store = cast(dict[str, object], store)
    raw = store.get("grid_size")
    if not isinstance(raw, list | tuple):
        return None
    grid = cast(list[object], raw)
    if len(grid) != 2:
        return None
    gw, gh = integer(grid[0]), integer(grid[1])
    if gw is None or gh is None or gw <= 0 or gh <= 0:
        return None
    racks: list[list[object]] = []
    raw_racks = store.get("racks")
    candidates = cast(list[object], raw_racks) if isinstance(raw_racks, list | tuple) else []
    for raw_rack in candidates[:MAX_FOOTPRINT_RACKS]:
        if not isinstance(raw_rack, dict):
            continue
        rack = cast(dict[str, object], raw_rack)
        kind = rack.get("type")
        shape = rack.get("shape")
        raw_pos = rack.get("position", [0, 0])
        if not isinstance(kind, str) or kind not in _DRAWN or not isinstance(shape, list | tuple) or not shape:
            continue
        shape = cast(list[object], shape)
        if any(not isinstance(row, list | tuple) or not row for row in shape):
            continue
        rows, cols = len(shape), len(cast(list[object], shape[0]))
        if any(len(cast(list[object], row)) != cols for row in shape) or not isinstance(raw_pos, list | tuple):
            continue
        pos = cast(list[object], raw_pos)
        if len(pos) != 2:
            continue
        x, y = integer(pos[0]), integer(pos[1])
        if x is None or y is None:
            continue
        w, h = (rows, cols) if rack.get("rotation", 0) in (90, 270) else (cols, rows)
        racks.append([x, y, w, h, kind])
    return {"grid": [gw, gh], "racks": racks}


def list_projects() -> list[dict[str, Any]]:
    """Project list with computed status badge."""
    projects: list[dict[str, Any]] = []
    if not _data.exists():
        return projects
    for d in _data.iterdir():
        meta_file = d / "metadata.json"
        if not d.is_dir() or not meta_file.exists():
            continue
        pid = d.name
        try:
            raw: object = read_json(meta_file)
            setups = list_setups(pid)
        except DamagedFile as e:
            # Listed with the reason and the name of its layout: left out, the store looked lost after an update.
            logger.warning(f"[projects] {pid}: {e}")
            raw, setups = None, list_setups(pid)
        except (OSError, ValueError) as e:
            # One unreadable file must not hide every other store.
            logger.warning(f"[projects] skipping {pid}: unreadable ({type(e).__name__}: {e})")
            continue
        damaged = not isinstance(raw, dict)
        meta: dict[str, Any] = cast(dict[str, Any], raw) if isinstance(raw, dict) else {
            "project_id": pid, "name": "", "store_type": "", "grid_size": None, "weekly_schedule": [],
            "created_at": "", "updated_at": "",
            "description": "The store's settings file (metadata.json) is damaged and cannot be read; its layouts and runs "
                           "are kept."}
        p_file = personas_path(pid)
        try:
            raw_personas: object = read_json(p_file) if p_file.exists() else []
            has_personas = isinstance(raw_personas, list) and bool(cast(list[object], raw_personas))
        except ValueError as e:   # damaged customers: the store is still listed, as setting up
            logger.warning(f"[projects] {pid}: {e}")
            has_personas = False
        has_run = any(s.get("runId") for s in setups) or bool(final_runs(pid))
        state = read_state(pid)
        active_sid = state.get("activeSetupId")
        has_store = False
        if active_sid:
            try:
                active = read_setup(pid, active_sid)
                has_store = active.get("store") is not None
                if has_store:
                    meta["footprint"] = _footprint(cast(dict[str, Any], active["store"]))
                    store = active["store"]
                    if damaged and isinstance(store, dict):
                        meta["name"] = str(cast(dict[str, object], store).get("name") or "")
            except FileNotFoundError:
                pass
            except ValueError as e:   # the layout last open is damaged; the others still are listed
                logger.warning(f"[projects] {pid}: {e}")
        if has_run:
            meta["status"] = "Simulated"
        elif has_store and has_personas:
            meta["status"] = "Ready"
        else:
            meta["status"] = "Setting up"
        projects.append(meta)
    projects.sort(key=lambda m: str(m.get("created_at") or ""), reverse=True)
    return projects


def load_project(project_id: str) -> dict[str, Any]:
    """Full project load: metadata + personas + state + setup summaries (readiness included)."""
    meta_file = metadata_path(project_id)
    if not meta_file.exists():
        raise FileNotFoundError(f"Project not found: {project_id}")
    p_file = personas_path(project_id)
    # setup summaries carry readiness here (same shape as GET /setups).
    from store_emulator.application.setups import get_setups as _get_setups
    setups = _get_setups(project_id)
    try:
        personas: object = read_json(p_file) if p_file.exists() else []
    except ValueError as e:   # damaged customers: the store opens and shows none (they can be written again)
        logger.warning(f"[projects] {project_id}: {e}")
        personas = []
    if not isinstance(personas, list):
        logger.warning("[projects] %s: personas.json must contain a customer array", project_id)
        personas = []
    return {
        "projectId": project_id,
        "metadata": read_json(meta_file),
        "personas": personas,
        "state": read_state(project_id),
        "setups": setups,
        "personasLocked": any(s.get("runId") for s in setups) or bool(final_runs(project_id)),
    }


def save_project_personas(
    project_id: str,
    personas: list[object],
) -> None:
    """Save personas unless a generation, running simulation, or history locks them."""
    if not metadata_path(project_id).is_file():
        raise FileNotFoundError(f"Project not found: {project_id}")

    with project_layout_transaction(project_id):
        setups = list_setups(project_id)
        if any(s.get("status") == "running" for s in setups):
            raise AppError("personas cannot be modified while a simulation is running.", 409)
        if has_run_history(project_id):
            raise AppError("personas cannot be modified because the project has simulation history. Create a new project.", 409)
        if find_active_generation(project_id, kind="persona"):
            raise AppError("personas cannot be modified while persona generation is in progress.", 409)
        write_json(personas_path(project_id), personas)

        meta_file = metadata_path(project_id)
        if meta_file.exists():
            meta: dict[str, Any] = read_json(meta_file)
            meta["updated_at"] = now_iso()
            write_json(meta_file, meta)


def update_project_metadata(
    project_id: str,
    name: str | None = None,
    description: str | None = None,
    address: str | None = None,
    customer_profile: str | None = None,
) -> None:
    meta_file = metadata_path(project_id)
    if not meta_file.exists():
        raise FileNotFoundError(f"Project not found: {project_id}")
    with setup_tree_transaction(project_id):
        meta = cast(dict[str, object], read_json(meta_file))
        meta["updated_at"] = now_iso()
        if name is not None:
            meta["name"] = name
        if description is not None:
            meta["description"] = description
        if address is not None:
            meta["address"] = address
        if customer_profile is not None:
            meta["customer_profile"] = customer_profile
        write_json(meta_file, meta)


def delete_project(project_id: str) -> None:
    project_dir = _data / project_id
    if not metadata_path(project_id).is_file():
        raise FileNotFoundError(f"Project not found: {project_id}")
    with project_layout_transaction(project_id):
        for pattern in ("runs/*/status.json", "generations/*/status.json", "optimizations/*/status.json",
                        "captures/*/status.json", "captures/*/lab/jobs/*/status.json", "marketing/*/*/status.json",
                        "synergy/*/status.json"):
            for status_path in project_dir.glob(pattern):
                try:
                    raw: object = read_json(status_path)
                except (OSError, ValueError):
                    continue
                if isinstance(raw, dict):
                    state = cast(dict[str, object], raw).get("status")
                    if state in ("pending", "running"):
                        raise AppError(f"cannot delete project while job '{status_path.parent.name}' is {state}. Wait until it finishes.", 409)
        remove_tree(project_dir)
        delete_project_images(project_id)


def create_project_without_layout(
    config: SimulationConfig,
    name: str,
    description: str,
    store_type: str,
    address: str,
    customer_profile: str,
    weekly_schedule: list[DaySchedule],
    supplemental_bytes: bytes | None,
    supplemental_filename: str = "",
    layout: TemplateLayoutRequest | None = None,
    starter_selection: Literal["automatic", "format"] = "format",
) -> dict[str, Any]:
    """Project + optional template layout/catalog selection + persona kick-off.

    spec §4.2 / §4.5 — supplemental bytes/filename are forwarded to the
    background summarize_supplemental call. At the time of the immediate
    response, metadata.supplemental_summary is still empty (filled async).
    """
    validate_weekly_schedule(weekly_schedule)
    if supplemental_bytes is not None and supplemental_filename.lower().endswith(".csv"):
        try:
            validate_customer_csv(supplemental_bytes)
        except CustomerCsvLimitError as exc:
            raise AppError(str(exc), 413) from exc
        except CustomerCsvError as exc:
            raise AppError(str(exc), 400) from exc
    if supplemental_bytes is not None and supplemental_filename.lower().endswith(".xlsx"):
        try:
            read_customer_workbook(supplemental_bytes)
        except WorkbookLimitError as exc:
            raise AppError(str(exc), 413) from exc
        except ValueError as exc:
            raise AppError(str(exc), 400) from exc
    pid = f"proj_{uuid.uuid4().hex[:8]}"
    now = now_iso()
    meta: dict[str, Any] = {
        "project_id": pid,
        "name": name,
        "description": description,
        "store_type": store_type,
        "grid_size": None,
        "weekly_schedule": [d.model_dump() for d in weekly_schedule],
        "address": address,
        "customer_profile": customer_profile,
        "supplemental_summary": "",
        "created_at": now,
        "updated_at": now,
    }
    initial: dict[str, object] | None = None
    currency = layout.currency if layout is not None else config.currency.upper()
    meta["currency"] = currency
    if layout is not None:
        # Validate and build before any project files are created.
        initial = prepare_template_layout(pid, layout)
        initial["name"] = name
        store = Store.model_validate(initial["store"])
        store.name = name
        store.weekly_schedule = weekly_schedule
        store.type = store_type
        if starter_selection == "automatic":
            store, assignments = select_initial_assortment(config, store, layout, description)
            initial["starter_selection"] = {"mode": "automatic", "assignments": [row.model_dump(mode="json") for row in assignments]}
        initial["store"] = store.model_dump(mode="json")
        meta["grid_size"] = list(store.grid_size)
    project_dir = _data / pid
    project_dir.mkdir(parents=True, exist_ok=True)
    write_json(metadata_path(pid), meta)
    write_json(personas_path(pid), [])

    if initial is None:
        initial = create_initial_setup(pid, store=None)
    else:
        write_json(setup_path(pid, str(initial["id"])), initial)
    write_state(pid, {"activeSetupId": initial["id"]})

    persona_gen_id = start_persona_generation(
        config=config.model_copy(update={"currency": currency}), project_id=pid, setup_id=str(initial["id"]),
        supplemental_bytes=supplemental_bytes,
        supplemental_filename=supplemental_filename,
    )

    from store_emulator.application.setups import setup_summary
    return {
        "metadata": meta,
        "setup": setup_summary(pid, initial),
        "personaGenId": persona_gen_id,
    }
