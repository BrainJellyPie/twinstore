@echo off
REM TwinStore fallback launcher for a source checkout (the release download has the TwinStore app icon).
REM First run downloads Python and the app's dependencies (a few minutes); later runs start in seconds.
REM Data stays in backend\.data.
setlocal
cd /d "%~dp0\..\.."
set "PATH=%USERPROFILE%\.local\bin;%PATH%"
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
