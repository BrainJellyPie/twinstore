import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from store_emulator.engine.files import read_text, replace_file

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
            # On disk before the rename: a power cut or crash right after it could otherwise leave the file empty or
            # full of NUL bytes (NTFS and ext4 both reorder the two).
            f.flush()
            os.fsync(f.fileno())
        replace_file(tmp, path)
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            logger.warning("Could not remove temporary JSON file %s", tmp, exc_info=True)


class DamagedFile(ValueError):
    """A saved file that is not JSON: empty, NUL bytes or cut short. Versions before 0.4.3 did not flush a file before
    replacing the old one, so a power cut or a forced shutdown right after a save could leave it so."""

    def __init__(self, path: Path, reason: str) -> None:
        try:
            shown = path.resolve().relative_to(Path(DATA_DIR).resolve()).as_posix()
        except ValueError:
            shown = path.name
        super().__init__(f"The saved file {shown} is damaged and cannot be read ({reason}). It was probably cut off "
                         "when TwinStore was stopped or the computer lost power while saving it.")
        self.path = path


def read_json(path: Path) -> Any:  # json.load returns dict | list; caller refines the type.
    try:
        return json.loads(read_text(path))
    except UnicodeDecodeError as e:
        raise DamagedFile(path, "not text") from e
    except json.JSONDecodeError as e:
        raise DamagedFile(path, "empty" if not e.doc.strip(" \t\r\n\0") else "cut off or not JSON") from e


def generate_setup_id() -> str:
    return f"setup_{uuid.uuid4().hex}"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
