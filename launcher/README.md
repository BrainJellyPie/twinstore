# TwinStore launcher

One Go source, one icon, every OS. Double-click → a boot screen opens in the browser → the app.

```
launcher/
  main.go, app.go, server.go   start uv + the backend, boot screen, reverse proxy to the backend
  paths.go, uv.go, desktop.go  app files / per-user folder, fetching uv, Linux menu entry
  proc_{unix,windows}.go       process groups, instance lock, Windows proxy settings, browser, macOS bundle detach
  boot.html                    the boot screen (embedded)
  icon/                        icon.html → render.mjs → pack.py → twinstore.ico / TwinStore.icns / twinstore.png
  winres/, macos/, tools/      Windows resources, Info.plist, universal Mach-O joiner
  scripts/                     fallback shell launchers for a source checkout
  build.sh                     builds dist/{TwinStore.exe, TwinStore.app, twinstore-linux-*}
```

- **Address**: `http://127.0.0.1:8000` (next free port if taken). The launcher shows the boot screen there, then
  proxies everything to the backend on a private port, so bookmarks keep working across restarts.
- **Second click**: a running launcher for the same app files is found through `running.json` in the per-user
  folder and simply reopened in the browser. A per-app-folder lock (`running-<hash>.lock`), held from before that
  check until the launcher ends, makes a click while the first launcher is still starting wait for it instead of
  starting a second server on the same data.
- **uv**: the launcher's own copy (`bin/` in the per-user folder) first; a uv on PATH or in `~/.local/bin` /
  `~/.cargo/bin` only from 0.8 on; otherwise the latest release is fetched (an older uv remains the offline
  fallback).
- **Network**: uv is told to trust the system's certificates (`UV_SYSTEM_CERTS`, `UV_NATIVE_TLS` before uv 0.11)
  unless the user set either, for networks that inspect HTTPS. On Windows a proxy set in the system settings
  (not a PAC script) becomes `HTTPS_PROXY`/`HTTP_PROXY`/`NO_PROXY` when none is set. `PYTHONHOME`, `PYTHONPATH`
  and `PYTHONSTARTUP` left by another Python are not passed on.
- **Stopping**: `POST /__twinstore/quit` (needs the `X-TwinStore: 1` header) from the app's Quit button (top right),
  its ⌘K palette or the boot screen, or Ctrl+C in a terminal. Closing the browser tab does not stop it; the app and
  the boot screen say so. The backend gets end-of-input on stdin and shuts down cleanly; the process tree is
  ended if it does not. Whenever the backend exits, what is left of its process group (llama-server) is ended on
  macOS and Linux; on Windows the backend's job object does that.
- **macOS**: the app files live inside `TwinStore.app/Contents/Resources/app` (one icon, survives Gatekeeper's
  read-only copy); data and the Python environment go to `~/Library/Application Support/TwinStore`.
- **Per-user folder**: Windows `%LOCALAPPDATA%\TwinStore`, macOS `~/Library/Application Support/TwinStore`,
  Linux `~/.local/share/twinstore` — uv, logs, `running.json`.

Build: `launcher/build.sh` (Go ≥ 1.23, Python 3). Test: `launcher/dist/twinstore-linux-x64 --smoke --no-browser`.
Re-render the icon: `node launcher/icon/render.mjs && python3 launcher/icon/pack.py` (Playwright + Pillow).
