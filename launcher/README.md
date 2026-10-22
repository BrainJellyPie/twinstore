# TwinStore launcher

One Go source, one icon, every OS. Double-click → a boot screen opens in the browser → the app.

```
launcher/
  main.go, app.go, server.go   start uv + the backend, boot screen, reverse proxy to the backend
  paths.go, uv.go, desktop.go  app files / per-user folder, fetching uv, Linux menu entry
  data.go                      where data and Python environment live; an earlier version's stores brought over
  proc_{unix,windows}.go       process groups, instance lock, Windows proxy settings, browser, macOS bundle detach
  boot.html                    the boot screen (embedded)
  icon/                        icon.html → render.mjs → pack.py → twinstore.ico / TwinStore.icns / twinstore.png
  winres/, macos/, tools/      Windows resources, Info.plist, universal Mach-O joiner
  scripts/                     fallback shell launchers for a source checkout
  build.sh                     builds dist/{TwinStore.exe, TwinStore.app, twinstore-linux-*}
```

- **Address**: `http://127.0.0.1:8000` (next free port if taken). The launcher shows the boot screen there, then
  proxies everything to the backend on a private port, so bookmarks keep working across restarts.
- **Second click, other versions**: one launcher at a time uses a data home, since every version shares the stores
  and the Python environment. It holds `running.lock` there until it ends, however it ends, and notes its address in
  `launcher.json` beside it. A click on the same app files reopens the running app in the browser (one still starting
  is awaited up to 20 s). A click on other app files (another version) asks the running launcher to quit
  (`POST /__twinstore/quit`), waits up to 30 s for the lock, logs "Stopped the TwinStore running from <folder> so this
  version can use your stores" and starts, on the port the other one left free. If it does not let go, the boot screen
  says "Another TwinStore (<folder>) is still running; quit it and try again", and Try again asks again. Launchers
  before the lock noted themselves in `running.json` by app folder: one for the same app files is reopened, a macOS one
  elsewhere (it used the same per-user data) is asked to quit, and Windows and Linux ones, which kept their data in
  their app folder, are left running.
- **Data**: the stores, their runs, settings and the local model (`.data`) and the Python environment (`venv`) live in
  the per-user folder on every OS, never in the app folder. A release is unpacked into a new folder, and the new
  version finds them there at once; uv installs only what changed. The boot screen shows the data folder at the
  bottom, and the log says `Data folder: …` at each start. A `PARASTORE_DATA_HOME` set in the environment wins for
  the data, relative to the app folder (`PARASTORE_DATA_HOME=backend` keeps a source checkout on `backend/.data`).
  The fallback scripts in `scripts/` use the same folders, but neither bring stores over nor check for a running app.
- **Update from a launcher that kept the data in the app folder** (Windows and Linux before this one): the first start
  that finds no `.data` in the per-user folder brings the stores over, shown as the *Your stores* step. Of the data
  folders that hold a store (a folder with `metadata.json`) it takes the one whose stores changed last:
  `backend/.data` of its own app folder (a new version unpacked over the old one), or of the app folders named in
  `logs/launcher.log` and `launcher.prev.log` (`Starting: uv run --project <app folder>/backend …`, `Data folder: …`).
  It copies, so the earlier version keeps working (delete its folder once the stores show up): files of 64 MB and
  more (the local model) are hard-linked when on the same drive, and the llama.cpp runtime (`local_vlm/bin`, fetched
  again) and unfinished files (`*.part`, `*.tmp-*`) are left out. The copy goes to `.data.migrating`, renamed to
  `.data` once complete, so a copy cut short is made again at the next start; one that fails stops the start, with
  Try again. The log names the folder it came from. With nothing to bring over, the server adds the sample stores.
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
  read-only copy); the data and the Python environment were always in the per-user folder there.
- **Per-user folder**: Windows `%LOCALAPPDATA%\TwinStore`, macOS `~/Library/Application Support/TwinStore`,
  Linux `$XDG_DATA_HOME/twinstore` (`~/.local/share/twinstore`) — `.data`, `venv`, uv (`bin/`), `logs/`,
  `running.json`. 0.4.2 kept Python environments for long Windows app folder paths in `venv\<hash>`; with those there
  the environment goes to `venv\app`, and the `<hash>` folders can be deleted.

Build: `launcher/build.sh` (Go ≥ 1.23, Python 3). Test: `launcher/dist/twinstore-linux-x64 --smoke --no-browser`.
Re-render the icon: `node launcher/icon/render.mjs && python3 launcher/icon/pack.py` (Playwright + Pillow).
