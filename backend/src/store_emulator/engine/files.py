"""File operations that hold on Windows as well.

Windows refuses to replace or open a file while another handle has it open without delete sharing (a reader
polling a status file, a virus scanner looking at a file just written): os.replace and open fail with
PermissionError for a moment where Linux and macOS would simply proceed. These retry briefly there.
"""

import os
import shutil
import stat
import sys
import time
from collections.abc import Callable
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


def remove_tree(path: Path) -> None:
    """shutil.rmtree that clears read-only flags and, on Windows, waits out files still open for a moment
    (a response being sent, a status read, a virus scan) instead of stopping half-way through a folder."""
    def retry(func: Callable[[str], object], target: str, error: BaseException) -> None:
        if not isinstance(error, PermissionError):
            raise error
        try:
            os.chmod(target, stat.S_IWRITE)
        except OSError:
            pass
        delay = 0.05
        for _ in range(8):
            try:
                func(target)
                return
            except FileNotFoundError:
                return
            except PermissionError:
                if sys.platform != "win32":
                    raise
                time.sleep(delay)
                delay = min(delay * 2, 0.5)
        func(target)

    shutil.rmtree(path, onexc=retry)
