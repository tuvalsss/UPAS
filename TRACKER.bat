@echo off
REM Outcome tracker loop — detects resolved positions, writes realized PnL,
REM refreshes adaptive strategy weights. Runs every 30 min.
cd /d "%~dp0"
call .venv\Scripts\activate.bat
title UPAS_TRACKER
python -m core.outcome_tracker
