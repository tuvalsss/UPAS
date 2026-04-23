@echo off
cd /d "%~dp0"
title UPAS CLI
set PYTHONIOENCODING=utf-8
set "PY=%~dp0.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
"%PY%" -m tools.cli
