@echo off
REM Quick push — stages, commits with timestamp or message, and pushes to origin/main
REM Usage: PUSH.bat [optional commit message]

cd /d "%~dp0"

if "%~1"=="" (
    set "MSG=update: %DATE% %TIME%"
) else (
    set "MSG=%*"
)

git add -A
git diff --cached --quiet
if %ERRORLEVEL%==0 (
    echo Nothing to commit.
    exit /b 0
)

git commit -m "%MSG%"
if %ERRORLEVEL% NEQ 0 (
    echo Commit failed.
    exit /b 1
)

git push
echo.
echo ✓ Pushed to origin/main
