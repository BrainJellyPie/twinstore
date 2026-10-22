import logging
import shutil
from pathlib import Path
from typing import cast

from .io import DATA_DIR, read_json, write_json

logger = logging.getLogger(__name__)

# backend/src/store_emulator/application/storage/seed.py → backend/sample_data
_SAMPLE_DATA_DIR = Path(__file__).resolve().parents[4] / "sample_data"
# The sample projects this data folder has been given: one the user deleted is not given again.
_OFFERED = "sample_projects.json"


def _offered(data_root: Path) -> set[str] | None:
    """The sample ids handed out before; None when there is no readable record."""
    try:
        raw: object = read_json(data_root / _OFFERED)
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        logger.warning(f"server start: could not read {_OFFERED}", exc_info=True)
        return None
    ids = cast(dict[str, object], raw).get("offered") if isinstance(raw, dict) else None
    return {str(i) for i in cast(list[object], ids)} if isinstance(ids, list) else None


def _has_projects(data_root: Path) -> bool:
    return any(d.is_dir() and (d / "metadata.json").is_file() for d in data_root.iterdir())


def seed_sample_projects() -> int:
    """Copy every `proj_*` directory under `backend/sample_data/` into `.data/` once.

    Gives a fresh data folder a ready-to-explore project on first boot. Existing projects are never overwritten, and
    a sample project the user deleted stays deleted: the ids handed out are kept in `.data/sample_projects.json`.
    A data folder that already holds projects but no record was seeded by an earlier version, so a sample missing
    from it was deleted there.
    """
    if not _SAMPLE_DATA_DIR.is_dir():
        return 0

    data_root = Path(DATA_DIR)
    data_root.mkdir(parents=True, exist_ok=True)

    samples = [p for p in sorted(_SAMPLE_DATA_DIR.iterdir()) if p.is_dir() and p.name.startswith("proj_")]
    recorded = _offered(data_root)
    offered: set[str]
    if recorded is not None:
        offered = recorded
    else:
        offered = {p.name for p in samples} if _has_projects(data_root) else set[str]()
    known = set(offered)
    copied = 0
    for sample in samples:
        destination = data_root / sample.name
        if destination.exists() or sample.name in offered:
            known.add(sample.name)
            continue
        shutil.copytree(sample, destination)
        logger.info(f"server start: seeded sample project {sample.name}")
        known.add(sample.name)
        copied += 1
    if known != recorded:
        try:
            write_json(data_root / _OFFERED, {"offered": sorted(known)})
        except OSError:
            logger.warning("server start: could not record the sample projects", exc_info=True)
    return copied
