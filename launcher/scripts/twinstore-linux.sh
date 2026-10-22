#!/usr/bin/env bash
# TwinStore fallback launcher for a source checkout (the release download has the TwinStore app icon).
# First run downloads Python and the app's dependencies (a few minutes); later runs start in seconds.
# The stores and the Python environment live in the per-user folder, as with the app icon ($XDG_DATA_HOME/twinstore;
# PARASTORE_DATA_HOME chooses another data folder). Unlike the app icon, this script does not bring over stores an
# earlier version kept in backend/.data (start the launcher once for that, or set PARASTORE_DATA_HOME=backend), and it
# does not check for a TwinStore already running on them: quit that first.
set -e
cd "$(dirname "$0")/../.."
home="${XDG_DATA_HOME:-$HOME/.local/share}/twinstore"
mkdir -p "$home"
export PARASTORE_DATA_HOME="${PARASTORE_DATA_HOME:-$home}"
export UV_PROJECT_ENVIRONMENT="$home/venv"
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
if ! command -v uv >/dev/null 2>&1; then
  echo "[TwinStore] Installing uv (Python package manager, one time)…"
  if command -v curl >/dev/null 2>&1; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
  else
    wget -qO- https://astral.sh/uv/install.sh | sh
  fi
  export PATH="$HOME/.local/bin:$PATH"
fi
uv run --project backend --frozen --with nodejs-wheel-binaries==24.19.0 python -m store_emulator.launcher "$@" || {
  status=$?
  echo
  echo "[TwinStore] Stopped with an error (code $status). See the messages above."
  if [ -t 0 ]; then read -r -p "Press Enter to close…" _; fi
  exit $status
}
