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
- **Second click, other versions**: one launcher at a time uses a data home, since every version shares the stores.
  It holds `running.lock` there until it ends, however it ends, and notes its address in `launcher.json` beside it.
  A click on the same app files reopens the running app in the browser (one still starting is awaited up to 20 s; one
  quitting, which `/__twinstore/ping` reports as `stopping`, is awaited until it lets go, and the click then starts
  TwinStore). Two read-only copies macOS made of the same downloaded version (App Translocation) count as the same
  app files. A click on other app files (another version) asks the running launcher to quit
  (`POST /__twinstore/quit`), waits up to 30 s for the lock, logs "Stopped the TwinStore running from <folder> so this
  version can use your stores" and starts, on the port the other one left free; if a second click on this version
  takes the stores first, it shows that one. If the other version does not let go, the boot screen says "Another
  TwinStore (<folder>) is still running; quit it and try again", and Try again asks again; one that holds the stores
  but does not answer is also named on the boot screen, with Try again. Launchers before the lock noted themselves in
  `running.json` by app folder: one for the same app files is reopened, a macOS one elsewhere (it used the same
  per-user data) is asked to quit, and Windows and Linux ones, which kept their data in their app folder, are left
  running.
- **Other web pages**: the launcher answers only its own pages. A request naming another origin, or one the browser
  marks cross-site that is not a plain visit, is refused; the launcher's own paths (`/__twinstore/*`, preflights
  included) never go on to the server, and the server's CORS headers are not passed on. The server itself accepts
  changes only from pages on this computer (and the origins `TWINSTORE_ALLOWED_ORIGINS` lists, comma-separated).
- **Data**: the stores, their runs, settings and the local model (`.data`) and the Python environment (`venv`) live in
  the per-user folder on every OS, never in the app folder. A release is unpacked into a new folder, and the new
  version finds them there at once; uv installs only what changed. The boot screen shows the data folder at the
  bottom, and the log says `Data folder: …` at each start. A `PARASTORE_DATA_HOME` set in the environment wins for
  the data, relative to the app folder (`PARASTORE_DATA_HOME=backend` keeps a source checkout on `backend/.data`);
  such a data folder gets a Python environment of its own in the per-user folder (`venv-<hash>`), since a launcher on
  it may run beside one on the per-user data. The fallback scripts in `scripts/` use the per-user folders, but neither
  bring stores over nor check for a running app.
- **Logs**: the launcher that holds the per-user data folder writes `logs/launcher.log` and keeps the previous run's as
  `launcher.prev.log`. Any other (app files not found, another launcher holding the stores, a data folder of the user's
  choosing, `--smoke` beside a running app, or an earlier launcher still writing `launcher.log` on Windows) writes
  `launcher.pid-<pid>.log`, removed after a week, so it never turns over the log of one that is running.
- **Update from a launcher that kept the data in the app folder** (Windows and Linux before this one): the first start
  that finds no `.data` in the per-user folder brings the stores over, shown as the *Your stores* step. Of the data
  folders that hold a store (a folder with `metadata.json`) it takes the one whose stores changed last:
  `backend/.data` of its own app folder (a new version unpacked over the old one), or of the app folders the launcher
  logs name (`Starting: uv run --project <app folder>/backend …`, `Data folder: …`). Every start notes those in
  `earlier-data.json` before any log turns over, and keeps them until the per-user `.data` exists, so starts that did
  not bring the stores over (app files not found, quit early) do not lose them. It copies, so the earlier version
  keeps working (delete its folder once the stores show up): model files of 64 MB and more in `local_vlm` are
  hard-linked when on the same drive, links to folders or files (a store moved to another disk) are followed, files
  OneDrive keeps in the cloud are read like any other (the llama.cpp runtime in `local_vlm/bin` too, so a local model
  the user already has starts without a download), and unfinished files (`*.part`, `*.tmp-*`), devices, pipes and
  sockets are left out. A file that cannot be read is
  left out and named in the log (the step says how many), except a store's `metadata.json`. The copy goes to
  `.data.migrating`, renamed to `.data` once complete, so a copy cut short is made again at the next start. A copy
  that fails, or a folder that may hold stores but cannot be read, stops the start, with Try again and Start without
  them (the stores stay where they are); the server would otherwise add the sample stores, and the stores would never
  be brought over. The log names the folder it came from. With nothing to bring over, the server adds the sample
  stores.
- **uv**: the launcher's own copy (`bin/` in the per-user folder) first; a uv on PATH or in `~/.local/bin` /
  `~/.cargo/bin` only from 0.11 on; otherwise the latest release is fetched (an older uv remains the offline
  fallback). A download that receives nothing for a minute is given up; a slow one that keeps going finishes. A uv an
  earlier TwinStore still runs (Windows cannot replace it) is renamed aside and removed by a later install.
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
  `running.lock` and `launcher.json` (in the data folder, when the user chose another), `earlier-data.json` until the
  stores are brought over. 0.4.2 kept Python environments for long Windows app folder paths in `venv\<hash>`; with
  those there the environment goes to `venv\app`, and the `<hash>` folders can be deleted.

Build: `launcher/build.sh` (Go ≥ 1.23, Python 3). Test: `launcher/dist/twinstore-linux-x64 --smoke --no-browser`.
Re-render the icon: `node launcher/icon/render.mjs && python3 launcher/icon/pack.py` (Playwright + Pillow).
