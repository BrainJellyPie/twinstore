@echo off
REM TwinStore fallback launcher for a source checkout (the release download has the TwinStore app icon).
REM First run downloads Python and the app's dependencies (a few minutes); later runs start in seconds.
REM The stores and the Python environment live in the per-user folder, as with TwinStore.exe: LOCALAPPDATA\TwinStore.
REM PARASTORE_DATA_HOME chooses another data folder. Unlike TwinStore.exe, this script does not bring over stores an
REM earlier version kept in backend\.data (start TwinStore.exe once for that, or set PARASTORE_DATA_HOME=backend), and it
REM does not check for a TwinStore already running on them: quit that first.
setlocal
cd /d "%~dp0\..\.."
set "TWINSTORE_HOME=%LOCALAPPDATA%\TwinStore"
if not exist "%TWINSTORE_HOME%" mkdir "%TWINSTORE_HOME%"
if not defined PARASTORE_DATA_HOME set "PARASTORE_DATA_HOME=%TWINSTORE_HOME%"
set "UV_PROJECT_ENVIRONMENT=%TWINSTORE_HOME%\venv"
REM TwinStore 0.4.2 kept environments for long app folder paths inside venv, which uv then refuses to use as one:
REM like TwinStore.exe, use venv\app when venv holds files but is no environment.
if not exist "%TWINSTORE_HOME%\venv\pyvenv.cfg" for /f "delims=" %%f in ('dir /b "%TWINSTORE_HOME%\venv" 2^>nul') do set "UV_PROJECT_ENVIRONMENT=%TWINSTORE_HOME%\venv\app"
set "PATH=%USERPROFILE%\.local\bin;%PATH%"
REM Read and write files as UTF-8 whatever the Windows code page.
set "PYTHONUTF8=1"
where uv >nul 2>nul
if errorlevel 1 (
  echo [TwinStore] Installing uv ^(Python package manager, one time^)...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
  set "PATH=%USERPROFILE%\.local\bin;%PATH%"
)
uv run --project backend --frozen --with nodejs-wheel-binaries==24.19.0 python -m store_emulator.launcher %*
if errorlevel 1 (
  echo.
  echo [TwinStore] Stopped with an error. See the messages above.
  pause
)
endlocal
