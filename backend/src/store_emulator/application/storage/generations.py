"""Progress store for async generation jobs (layout/persona).

Each job is tracked via .data/{pid}/generations/{gen_id}/status.json.
status: pending → running → completed | failed.
kind: "layout" | "persona".
"""

import logging
import uuid
from pathlib import Path
from typing import Any, Literal

from store_emulator.application.storage.io import (
    DATA_DIR, read_json, write_json, now_iso,
)

logger = logging.getLogger(__name__)

GenerationKind = Literal["layout", "persona"]
GenerationStatus = Literal["pending", "running", "completed", "failed"]


def generations_dir(project_id: str) -> Path:
    return Path(DATA_DIR) / project_id / "generations"


def generation_dir(project_id: str, gen_id: str) -> Path:
    return generations_dir(project_id) / gen_id


def status_path(project_id: str, gen_id: str) -> Path:
    return generation_dir(project_id, gen_id) / "status.json"


def generate_gen_id() -> str:
    return f"gen_{uuid.uuid4().hex[:10]}"


def init_generation(
    project_id: str,
    setup_id: str,
    kind: GenerationKind,
) -> str:
    """Register a new generation with status=pending and return its gen_id."""
    gen_id = generate_gen_id()
    generation_dir(project_id, gen_id).mkdir(parents=True, exist_ok=True)
    write_status(project_id, gen_id, "pending", kind=kind, setup_id=setup_id)
    return gen_id


def write_status(
    project_id: str,
    gen_id: str,
    status: GenerationStatus,
    *,
    kind: GenerationKind | None = None,
    setup_id: str | None = None,
    error: str | None = None,
    progress: dict[str, Any] | None = None,
) -> None:
    """Update status.json in place; only the fields provided are overwritten."""
    path = status_path(project_id, gen_id)
    data: dict[str, Any] = read_json(path) if path.exists() else {"created_at": now_iso()}
    data["status"] = status
    data["updated_at"] = now_iso()
    if kind is not None:
        data["kind"] = kind
    if setup_id is not None:
        data["setup_id"] = setup_id
    if error is not None:
        data["error"] = error
    if progress is not None:
        data["progress"] = progress
    write_json(path, data)


def read_status(project_id: str, gen_id: str) -> dict[str, Any]:
    path = status_path(project_id, gen_id)
    if not path.exists():
        raise FileNotFoundError(f"Generation not found: {gen_id}")
    return read_json(path)


def list_generations(project_id: str, setup_id: str | None = None) -> list[dict[str, Any]]:
    """List generations for a project; optional setup_id filter."""
    root = generations_dir(project_id)
    if not root.exists():
        return []
    results: list[dict[str, Any]] = []
    for gd in root.iterdir():
        if not gd.is_dir():
            continue
        sf = gd / "status.json"
        if not sf.exists():
            continue
        data = read_json(sf)
        if setup_id and data.get("setup_id") != setup_id:
            continue
        results.append({"gen_id": gd.name, **data})
    results.sort(key=lambda x: str(x.get("created_at", "")), reverse=True)
    return results


def find_active_generation(
    project_id: str,
    setup_id: str | None = None,
    kind: GenerationKind | None = None,
) -> dict[str, Any] | None:
    """Return one in-flight generation for the project or specified setup, or None.

    When ``kind`` is given, restricts the search to that kind.
    """
    for g in list_generations(project_id, setup_id):
        if g.get("status") not in ("pending", "running"):
            continue
        if kind and g.get("kind") != kind:
            continue
        return g
    return None


def recover_running_generations() -> int:
    """Server-startup recovery: move every pending/running generation to failed. Returns count."""
    recovered = 0
    data_root = Path(DATA_DIR)
    if not data_root.exists():
        return 0
    for proj_dir in data_root.iterdir():
        if not proj_dir.is_dir() or not proj_dir.name.startswith("proj_"):
            continue
        gen_root = proj_dir / "generations"
        if not gen_root.exists():
            continue
        for gd in gen_root.iterdir():
            if not gd.is_dir():
                continue
            sf = gd / "status.json"
            if not sf.exists():
                continue
            data = read_json(sf)
            if data.get("status") in ("pending", "running"):
                data["status"] = "failed"
                data["error"] = "interrupted by server restart"
                data["updated_at"] = now_iso()
                write_json(sf, data)
                recovered += 1
                logger.info(f"[recovery] {proj_dir.name}/{gd.name}: {data.get('kind')} generation → failed")
    return recovered
