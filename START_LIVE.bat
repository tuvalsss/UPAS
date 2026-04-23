@echo off
REM ============================================================
REM UPAS — LIVE AUTONOMOUS TRADING
REM Double-click this file to start continuous autonomous trading.
REM Press Ctrl+C in the window to stop gracefully (checkpoint saved).
REM ============================================================
cd /d "%~dp0"
title UPAS LIVE — DO NOT CLOSE
echo ============================================================
echo  UPAS LIVE AUTONOMOUS MODE
echo  Scanning every 60s. Max 1 trade/cycle. Max $8/trade.
echo  Press Ctrl+C to stop gracefully.
echo ============================================================
echo.

REM Force LIVE flags
powershell -NoProfile -Command "(Get-Content .env) -replace 'AUTO_EXECUTE=false','AUTO_EXECUTE=true' -replace 'DRY_RUN=true','DRY_RUN=false' | Set-Content .env"

set PYTHONIOENCODING=utf-8
set "PY=%~dp0.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
"%PY%" -m core.scheduler --non-interactive

echo.
echo UPAS stopped. Reverting .env to safe DRY mode...
powershell -NoProfile -Command "(Get-Content .env) -replace 'AUTO_EXECUTE=true','AUTO_EXECUTE=false' -replace 'DRY_RUN=false','DRY_RUN=true' | Set-Content .env"
echo Done. Press any key to close.
pause > nul
