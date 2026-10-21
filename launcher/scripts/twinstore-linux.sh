#!/usr/bin/env bash
# TwinStore fallback launcher for a source checkout (the release download has the TwinStore app icon).
# First run downloads Python and the app's dependencies (a few minutes); later runs start in seconds.
# Data stays in backend/.data.
set -e
cd "$(dirname "$0")/../.."
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
