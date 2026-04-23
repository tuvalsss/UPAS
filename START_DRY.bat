@echo off
REM UPAS — DRY RUN (simulation only, no real orders)
cd /d "%~dp0"
title UPAS DRY RUN
powershell -NoProfile -Command "(Get-Content .env) -replace 'AUTO_EXECUTE=true','AUTO_EXECUTE=false' -replace 'DRY_RUN=false','DRY_RUN=true' | Set-Content .env"
set PYTHONIOENCODING=utf-8
set "PY=%~dp0.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
"%PY%" -m core.scheduler --non-interactive
pause
