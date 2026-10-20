"""One-click launcher: prepare the web UI if needed, start the server, open the browser.

Started by the double-click scripts at the repository root (Parastore-Windows.bat,
Parastore-macOS.command, Parastore-Linux.sh) through `uv`, which fetches Python and every
dependency on first run. Nothing else needs to be installed:

- If `frontend/dist` is missing (a git checkout rather than a release zip), the UI is built once
  with Node.js — the system one if present, otherwise the `nodejs-wheel-binaries` package that the
  launch scripts add to the environment.
- The server listens on 127.0.0.1 only, on the first free port from 8000.
"""

import argparse
import importlib.util
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
DIST = FRONTEND / "dist"
PNPM = "pnpm@10.33.0"


def _say(msg: str) -> None:
    print(f"[Parastore] {msg}", flush=True)


def _node_command() -> list[str] | None:
    """How to run `npx`: the system Node.js, or the pip-installed `nodejs` package."""
    npx = shutil.which("npx")
    if npx:
        return [npx]
    if importlib.util.find_spec("nodejs") is None:  # nodejs-wheel-binaries, added by the launch scripts
        return None
    return [sys.executable, "-m", "nodejs.npx"]


def _ui_is_stale() -> bool:
    if not (DIST / "index.html").is_file():
        return True
    built = (DIST / "index.html").stat().st_mtime
    sources = [p for p in (FRONTEND / "src").rglob("*") if p.is_file()] if (FRONTEND / "src").is_dir() else []
    return any(p.stat().st_mtime > built for p in sources)


def build_ui(force: bool = False) -> bool:
    """Make sure frontend/dist exists and matches the sources. Returns True when a UI is available.

    Release zips ship a prebuilt UI (marked by dist/.prebuilt) and never rebuild; in a git checkout
    the UI is rebuilt when any source file is newer than the last build.
    """
    has_ui = (DIST / "index.html").is_file()
    has_sources = (FRONTEND / "package.json").is_file() and (FRONTEND / "src").is_dir()
    prebuilt = (DIST / ".prebuilt").is_file()
    if has_ui and not force and (prebuilt or not has_sources or not _ui_is_stale()):
        return True
    if not has_sources:
        return has_ui
    npx = _node_command()
    if npx is None:
        _say("Node.js not found and the bundled Node package is missing — serving the API only.")
        return has_ui
    _say("Preparing the web interface (first run or after an update, ~1–3 minutes)…")
    env = {**os.environ, "VITE_API_URL": "", "CI": "1", "npm_config_update_notifier": "false"}
    steps = [
        [*npx, "--yes", PNPM, "install", "--frozen-lockfile", "--prefer-offline"],
        [*npx, "--yes", PNPM, "exec", "vite", "build"],
    ]
    for cmd in steps:
        if subprocess.run(cmd, cwd=FRONTEND, env=env, check=False).returncode != 0:
            _say("Building the web interface failed (see above). The API still starts.")
            return (DIST / "index.html").is_file()
    _say("Web interface ready.")
    return True


def free_port(start: int, host: str) -> int:
    for port in range(start, start + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind((host, port))
            except OSError:
                continue
            return port
    raise RuntimeError(f"no free port in {start}–{start + 49}")


def _open_when_ready(url: str, open_browser: bool) -> None:
    for _ in range(240):
        try:
            with urllib.request.urlopen(f"{url}/api/health", timeout=2) as r:
                if r.status == 200:
                    break
        except OSError:
            time.sleep(0.5)
    _say(f"Parastore is running at {url}  (close this window or press Ctrl+C to stop)")
    if open_browser:
        webbrowser.open(url)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="parastore-app", description="Start Parastore and open it in the browser.")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PARASTORE_PORT", "8000")))
    parser.add_argument("--host", default=os.environ.get("PARASTORE_HOST", "127.0.0.1"))
    parser.add_argument("--no-browser", action="store_true", help="do not open a browser tab")
    parser.add_argument("--rebuild-ui", action="store_true", help="rebuild the web interface")
    args = parser.parse_args(argv)

    os.chdir(BACKEND)  # data lives in backend/.data, next to the sample projects
    build_ui(force=args.rebuild_ui)
    port = free_port(args.port, args.host)
    url = f"http://{'127.0.0.1' if args.host in ('0.0.0.0', '::') else args.host}:{port}"
    threading.Thread(target=_open_when_ready, args=(url, not args.no_browser), daemon=True).start()

    import uvicorn

    _say(f"Starting on {url} …")
    uvicorn.run("store_emulator.server.main:app", host=args.host, port=port, log_level="warning")
    return 0


if __name__ == "__main__":
    sys.exit(main())
