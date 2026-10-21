import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DATA_DIR = ".data"
logger = logging.getLogger(__name__)


def write_json(path: Path, data: object) -> None:
    """Atomic JSON write: serialize to tmp file, then os.replace.

    Prevents partial/empty files under concurrent writes. If the write fails
    mid-way, the existing file is preserved.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp-{uuid.uuid4().hex[:6]}")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        os.replace(tmp, path)
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            logger.warning("Could not remove temporary JSON file %s", tmp, exc_info=True)


def read_json(path: Path) -> Any:  # json.load returns dict | list; caller refines the type.
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def generate_setup_id() -> str:
    return f"setup_{uuid.uuid4().hex}"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
