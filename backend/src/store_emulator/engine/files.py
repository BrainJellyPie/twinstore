"""File operations that hold on Windows as well.

Windows refuses to replace or open a file while another handle has it open without delete sharing (a reader
polling a status file, a virus scanner looking at a file just written): os.replace and open fail with
PermissionError for a moment where Linux and macOS would simply proceed. These retry briefly there.
"""

import os
import sys
import time
from pathlib import Path

_TRIES = 12  # about 2 s in all


def replace_file(src: Path, dst: Path) -> None:
    """os.replace(src, dst), retried while Windows reports the file as in use."""
    delay = 0.01
    for _ in range(_TRIES - 1):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if sys.platform != "win32":
                raise
            time.sleep(delay)
            delay = min(delay * 2, 0.25)
    os.replace(src, dst)


def read_text(path: Path) -> str:
    """UTF-8 text of a file, retried while Windows reports it as being replaced."""
    delay = 0.01
    for _ in range(_TRIES - 1):
        try:
            return path.read_text(encoding="utf-8")
        except PermissionError:
            if sys.platform != "win32":
                raise
            time.sleep(delay)
            delay = min(delay * 2, 0.25)
    return path.read_text(encoding="utf-8")
