# Quick start — no programming needed

## 한국어

1. **내려받기**: GitHub 저장소의 **Releases**에서 `parastore-<버전>.zip`을 내려받아 압축을 풉니다.
   (Releases가 없으면 초록색 **Code → Download ZIP**도 됩니다. 이 경우 첫 실행 때 화면 빌드가 1~3분 더 걸립니다.)
2. **실행**: 압축을 푼 폴더에서 운영체제에 맞는 파일을 **더블클릭**합니다.

   | 운영체제 | 더블클릭할 파일 | 처음 한 번만 |
   | --- | --- | --- |
   | Windows | `Parastore-Windows.bat` | "Windows의 PC 보호" 창이 뜨면 **추가 정보 → 실행** |
   | macOS | `Parastore-macOS.command` | 파일을 **우클릭 → 열기 → 열기** (보안 확인) |
   | Linux | `Parastore-Linux.sh` | 파일 관리자에서 **실행** 선택, 또는 `scripts/install-linux-shortcut.sh`로 메뉴에 등록 |

3. **사용**: 잠시 뒤 브라우저가 자동으로 열립니다(`http://127.0.0.1:8000`). 열리지 않으면 검은 창에 표시된 주소를 브라우저에 붙여넣으세요.
   - 첫 실행은 Python과 필요한 구성요소를 자동으로 내려받느라 몇 분 걸립니다. 다음부터는 몇 초면 시작됩니다.
   - 끝낼 때는 검은 창(터미널)을 닫거나 `Ctrl+C`를 누릅니다.
   - 데이터는 폴더 안 `backend/.data`에만 저장되고 외부로 보내지지 않습니다.

**API 키 없이도** 샘플 매장과 *Rule-based* 엔진으로 바로 시뮬레이션할 수 있습니다. LLM/VLM 쇼퍼를 쓰려면 오른쪽 위 **Models**에서
OpenAI·Anthropic·Gemini·Qwen 키를 입력하거나, vLLM·Ollama·llama.cpp 같은 로컬 서버 주소를 넣으세요.

문제가 생기면: 인터넷 연결(첫 실행 시 필요)을 확인하고, 검은 창의 마지막 메시지를 그대로 알려주세요.

## English

1. **Download** `parastore-<version>.zip` from the repository's **Releases** page and unzip it
   (or **Code → Download ZIP**; the first start then builds the UI, which takes 1–3 extra minutes).
2. **Double-click** the launcher for your system:

   | System | Double-click | First time only |
   | --- | --- | --- |
   | Windows | `Parastore-Windows.bat` | If SmartScreen appears: **More info → Run anyway** |
   | macOS | `Parastore-macOS.command` | **Right-click → Open → Open** (Gatekeeper prompt) |
   | Linux | `Parastore-Linux.sh` | Choose **Run** in the file manager, or add a menu entry with `scripts/install-linux-shortcut.sh` |

3. Your browser opens at `http://127.0.0.1:8000` (the console window shows the address if it does not).
   The first start downloads Python and the dependencies (a few minutes); later starts take seconds.
   Close the console window or press `Ctrl+C` to stop. Data stays in `backend/.data` on your machine.

Without any API key you can simulate the sample store with the *Rule-based* engine right away. To use LLM/VLM
shoppers, open **Models** (top right) and add an OpenAI, Anthropic, Gemini or Qwen key, or the address of a local
vLLM / Ollama / llama.cpp server.

### What the launchers do

They install [uv](https://docs.astral.sh/uv/) if it is missing (one small download into your user folder), then run
`uv run --project backend python -m store_emulator.launcher`, which fetches Python 3.13 and the backend dependencies,
builds the web UI if the zip did not include one (using a Node.js package fetched the same way — nothing to install),
picks a free port from 8000, starts the server on `127.0.0.1` only, and opens the browser. Options:
`--port 8100`, `--no-browser`, `--rebuild-ui`.
