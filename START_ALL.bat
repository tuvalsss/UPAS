@echo off
REM ============================================================
REM UPAS — Unified Launcher (LIVE) with preflight + error capture
REM ============================================================
setlocal EnableDelayedExpansion
cd /d "%~dp0"
title UPAS MASTER - close to stop all

set "PY=%~dp0.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
set PYTHONIOENCODING=utf-8

if not exist "%~dp0logs" mkdir "%~dp0logs"

echo ============================================================
echo  UPAS LIVE LAUNCHER
echo  Python: %PY%
echo ============================================================
echo.

REM Flip .env to LIVE
powershell -NoProfile -Command "(Get-Content '.env') -replace 'AUTO_EXECUTE=false','AUTO_EXECUTE=true' -replace 'DRY_RUN=true','DRY_RUN=false' | Set-Content '.env'" 2>nul

REM ── Preflight ──────────────────────────────────────────────
echo [preflight] python version:
"%PY%" --version
if errorlevel 1 (
    echo [ERROR] python not found at %PY%
    echo.
    echo Press any key to close...
    pause >nul
    exit /b 1
)

echo [preflight] importing core.scheduler ...
"%PY%" -c "import core.scheduler" 1> "%~dp0logs\preflight_scheduler.log" 2>&1
if errorlevel 1 (
    echo [ERROR] core.scheduler import failed:
    echo ----------------------------------------
    type "%~dp0logs\preflight_scheduler.log"
    echo ----------------------------------------
    echo.
    echo Log saved to: logs\preflight_scheduler.log
    echo Press any key to close...
    pause >nul
    exit /b 1
)

echo [preflight] importing tools.dashboard ...
"%PY%" -c "import tools.dashboard" 1> "%~dp0logs\preflight_dashboard.log" 2>&1
if errorlevel 1 (
    echo [ERROR] tools.dashboard import failed:
    echo ----------------------------------------
    type "%~dp0logs\preflight_dashboard.log"
    echo ----------------------------------------
    echo Press any key to close...
    pause >nul
    exit /b 1
)

echo [preflight] importing tools.cli ...
"%PY%" -c "import tools.cli" 1> "%~dp0logs\preflight_cli.log" 2>&1
if errorlevel 1 (
    echo [ERROR] tools.cli import failed:
    echo ----------------------------------------
    type "%~dp0logs\preflight_cli.log"
    echo ----------------------------------------
    echo Press any key to close...
    pause >nul
    exit /b 1
)

echo [preflight] OK
echo.

REM ── Launch children ────────────────────────────────────────
echo [launcher] starting SCHEDULER window...
start "UPAS_SCHEDULER" cmd /k ""%PY%" -m core.scheduler --non-interactive"
timeout /t 3 /nobreak >nul

echo [launcher] starting DASHBOARD window...
start "UPAS_DASHBOARD" cmd /k ""%PY%" -m tools.dashboard"
timeout /t 2 /nobreak >nul

echo.
echo [launcher] CLI below. Type 'help' or 'exit'.
echo.
"%PY%" -m tools.cli
set CLI_EXIT=%errorlevel%

echo.
echo [launcher] shutting down (CLI exit %CLI_EXIT%)...
taskkill /FI "WINDOWTITLE eq UPAS_SCHEDULER*" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq UPAS_DASHBOARD*" /T /F >nul 2>&1
echo [launcher] done.
timeout /t 2 /nobreak >nul
endlocal
