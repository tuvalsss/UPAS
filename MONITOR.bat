@echo off
REM Position monitor — stop-loss + take-profit loop
cd /d "%~dp0"
call .venv\Scripts\activate.bat
title UPAS_MONITOR
python -m core.position_monitor
