# TwinStore launcher

One Go source, one icon, every OS. Double-click → a boot screen opens in the browser → the app.

```
launcher/
  main.go, app.go, server.go   start uv + the backend, boot screen, reverse proxy to the backend
  paths.go, uv.go, desktop.go  app files / per-user folder, fetching uv, Linux menu entry
  proc_{unix,windows}.go       process groups, browser, macOS bundle detach
  boot.html                    the boot screen (embedded)
  icon/                        icon.html → render.mjs → pack.py → twinstore.ico / TwinStore.icns / twinstore.png
  winres/, macos/, tools/      Windows resources, Info.plist, universal Mach-O joiner
  scripts/                     fallback shell launchers for a source checkout
  build.sh                     builds dist/{TwinStore.exe, TwinStore.app, twinstore-linux-*}
```

- **Address**: `http://127.0.0.1:8000` (next free port if taken). The launcher shows the boot screen there, then
  proxies everything to the backend on a private port, so bookmarks keep working across restarts.
- **Second click**: a running launcher for the same app files is found through `running.json` in the per-user
  folder and simply reopened in the browser.
- **Stopping**: `POST /__twinstore/quit` (needs the `X-TwinStore: 1` header) from the app's ⌘K palette or the boot
  screen, or Ctrl+C in a terminal. The backend gets end-of-input on stdin and shuts down cleanly; the process tree is
  ended if it does not.
- **macOS**: the app files live inside `TwinStore.app/Contents/Resources/app` (one icon, survives Gatekeeper's
  read-only copy); data and the Python environment go to `~/Library/Application Support/TwinStore`.
- **Per-user folder**: Windows `%LOCALAPPDATA%\TwinStore`, macOS `~/Library/Application Support/TwinStore`,
  Linux `~/.local/share/twinstore` — uv, logs, `running.json`.

Build: `launcher/build.sh` (Go ≥ 1.23, Python 3). Test: `launcher/dist/twinstore-linux-x64 --smoke --no-browser`.
Re-render the icon: `node launcher/icon/render.mjs && python3 launcher/icon/pack.py` (Playwright + Pillow).
