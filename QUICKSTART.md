# Quick start — no programming needed

## 한국어

1. **내려받기**: GitHub 저장소의 **Releases**에서 내 컴퓨터에 맞는 파일 하나를 받아 압축을 풉니다.

   | 컴퓨터 | 받을 파일 | 더블클릭할 아이콘 |
   | --- | --- | --- |
   | Windows 10/11 | `TwinStore-<버전>-windows-x64.zip` | `TwinStore.exe` |
   | macOS 11 이상 (Apple 실리콘·Intel 모두) | `TwinStore-<버전>-macos.zip` | `TwinStore.app` |
   | Linux (x64 / arm64) | `TwinStore-<버전>-linux-*.tar.gz` | `twinstore` |

2. **실행**: **TwinStore 아이콘 하나만 더블클릭**하면 됩니다. 운영체제와 상관없이 같은 아이콘, 같은 동작입니다.
   - 브라우저가 바로 열리고 시작 화면(진행 단계·로그)이 보이다가, 준비되면 앱으로 자동 전환됩니다 (`http://127.0.0.1:8000`).
   - 첫 실행만 Python과 필요한 구성요소를 자동으로 내려받느라 몇 분 걸립니다. 다음부터는 몇 초면 시작됩니다.
   - 아이콘을 다시 누르면 이미 실행 중인 앱이 다시 열립니다.
   - **브라우저 탭을 닫아도 TwinStore는 종료되지 않습니다.** 다 쓰셨으면 앱 오른쪽 위 **종료** 버튼(또는 `Ctrl+K`/`⌘K` →
     **TwinStore 종료**, 시작 화면의 **Quit**)을 눌러 주세요. 켜 둔 채로는 메모리를 계속 쓰고, 앱을 업데이트하거나 지울 수 없습니다.

3. **처음 한 번만 나오는 보안 확인**
   - Windows: "Windows의 PC 보호" 창 → **추가 정보 → 실행**
   - macOS: 아이콘 **우클릭 → 열기 → 열기**. macOS 15 이상에서 막히면 **시스템 설정 → 개인정보 보호 및 보안 → 그래도 열기**
   - Linux: 첫 실행 뒤 앱 메뉴에 TwinStore 아이콘이 자동으로 추가됩니다.

**API 키 없이도** 샘플 매장과 *Rule-based* 엔진으로 바로 시뮬레이션할 수 있습니다. LLM/VLM 쇼퍼를 쓰려면 상단의 **Models**에서
OpenAI·Anthropic·Gemini·Qwen 키를 입력하거나, vLLM·Ollama·llama.cpp 같은 로컬 서버 주소를 넣으세요.

데이터는 내 컴퓨터에만 저장됩니다 (Windows·Linux: 압축을 푼 폴더의 `app/backend/.data`, macOS: `~/Library/Application Support/TwinStore`).
문제가 생기면 시작 화면의 **Copy log**로 로그를 복사해 알려주세요.

## English

1. **Download** the one file for your computer from the repository's **Releases** page and unpack it:

   | Computer | Download | Double-click |
   | --- | --- | --- |
   | Windows 10/11 | `TwinStore-<version>-windows-x64.zip` | `TwinStore.exe` |
   | macOS 11+ (Apple silicon or Intel) | `TwinStore-<version>-macos.zip` | `TwinStore.app` |
   | Linux x64 / arm64 | `TwinStore-<version>-linux-*.tar.gz` | `twinstore` |

2. **Double-click the TwinStore icon** — the same icon and the same behavior on every system.
   Your browser opens a boot screen with live progress and switches to the app when it is ready (`http://127.0.0.1:8000`).
   The first start downloads Python and the dependencies (a few minutes); later starts take seconds. Clicking the icon
   again reopens the running app. **Closing the browser tab does not stop TwinStore**: when you are done, press **Quit**
   at the top right of the app (or `Ctrl+K` / `⌘K` → **Quit TwinStore**, or **Quit** on the boot screen). Left running,
   it keeps using memory, and the app cannot be updated or deleted.

3. **First time only**: Windows SmartScreen → **More info → Run anyway**. macOS → **right-click → Open → Open**
   (macOS 15+: **System Settings → Privacy & Security → Open Anyway**). Linux adds TwinStore to the app menu on first start.

Without any API key you can simulate the sample store with the *Rule-based* engine right away. To use LLM/VLM
shoppers, open **Models** and add an OpenAI, Anthropic, Gemini or Qwen key, or the address of a local vLLM / Ollama /
llama.cpp server. **Capture** (shelf photo → planogram) works out of the box; for the Grounding DINO detector run
`uv sync --extra capture` once in `backend` (it downloads PyTorch, which is large).

Data stays on your machine: `app/backend/.data` next to the launcher on Windows and Linux,
`~/Library/Application Support/TwinStore` on macOS. If something goes wrong, **Copy log** on the boot screen.

### What the launcher does

`launcher/` is a small Go program built for each OS from one source (`launcher/build.sh`). It finds its app files,
downloads [uv](https://docs.astral.sh/uv/) into its own folder if none is installed (no admin rights, no shell profile
edits), runs `uv run --project backend python -m store_emulator.launcher`, which fetches Python 3.13 and the backend
dependencies, and serves the boot screen and then the app at `127.0.0.1` only. Options: `--port 8100`, `--no-browser`,
`--rebuild-ui`, `--smoke`. Its log is in the per-user TwinStore folder (`logs/launcher.log`).

**From a source checkout** (no release): build the launcher once with Go (`launcher/build.sh`, outputs in
`launcher/dist`), or use the fallback scripts `launcher/scripts/twinstore-{windows.bat,macos.command,linux.sh}`;
the first start then also builds the web interface (1–3 minutes).
