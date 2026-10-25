"""Recover file-backed jobs whose worker was interrupted by a server restart."""

import logging
from pathlib import Path
from typing import cast

from store_emulator.application.storage.io import DATA_DIR, now_iso, read_json, write_json

logger = logging.getLogger(__name__)

_STATUS_PATTERNS = (
    "*/runs/*/status.json",
    "*/optimizations/*/status.json",
    "*/synergy/*/status.json",
    "*/online/runs/*/status.json",
    "*/captures/*/status.json",
    "*/captures/*/lab/jobs/*/status.json",
)


def recover_interrupted_jobs() -> int:
    """Fail interrupted jobs while preserving their inputs, partial outputs, and finished results."""
    recovered = 0
    for pattern in _STATUS_PATTERNS:
        for path in Path(DATA_DIR).glob(pattern):
            try:
                raw: object = read_json(path)
                if not isinstance(raw, dict):
                    raise ValueError("job status must be an object")
                data = cast(dict[str, object], raw)
                if data.get("status") not in ("pending", "running"):
                    continue
                data.update({"status": "failed", "error": "interrupted by server restart; start a new job to retry",
                             "finished_at": now_iso()})
                for field in ("phase", "stage"):
                    if field in data:
                        data[field] = "interrupted"
                write_json(path, data)
                recovered += 1
            except (OSError, ValueError) as exc:
                logger.warning("Could not recover job %s: %s", path, exc)
    return recovered
