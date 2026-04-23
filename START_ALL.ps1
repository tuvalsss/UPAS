# START_ALL.ps1 — Unified UPAS launcher (LIVE mode)
# Spawns scheduler + dashboard in separate PowerShell windows, keeps CLI in foreground.
# Closing this window (or typing 'exit' in CLI) kills every child.

$ErrorActionPreference = "Continue"
$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ROOT
$env:PYTHONIOENCODING = "utf-8"

$py = Join-Path $ROOT ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

# ── Force LIVE mode in .env ─────────────────────────────────
Write-Host "[launcher] setting .env to LIVE (AUTO_EXECUTE=true, DRY_RUN=false)..."
$envFile = Join-Path $ROOT ".env"
if (Test-Path $envFile) {
    $c = Get-Content $envFile -Raw
    $c = $c -replace 'AUTO_EXECUTE=false','AUTO_EXECUTE=true'
    $c = $c -replace 'DRY_RUN=true','DRY_RUN=false'
    Set-Content -Path $envFile -Value $c -Encoding UTF8 -NoNewline
}

# ── Spawn child windows ─────────────────────────────────────
$procs = @()

function Spawn-Window {
    param([string]$Title, [string[]]$PyArgs)
    $argList = @(
        "-NoExit", "-NoProfile",
        "-Command",
        "`$host.UI.RawUI.WindowTitle = '$Title'; Set-Location '$ROOT'; `$env:PYTHONIOENCODING='utf-8'; & '$py' $($PyArgs -join ' ')"
    )
    $p = Start-Process -FilePath "powershell.exe" -ArgumentList $argList -PassThru -WorkingDirectory $ROOT
    Write-Host "[launcher] started '$Title' (pid=$($p.Id))"
    return $p
}

try {
    Write-Host "============================================================"
    Write-Host " UPAS — Unified Launcher (LIVE)"
    Write-Host " Close THIS window or type 'exit' in CLI to stop everything."
    Write-Host "============================================================"

    $procs += Spawn-Window "UPAS_SCHEDULER" @("-m", "core.scheduler", "--non-interactive")
    Start-Sleep -Seconds 3
    $procs += Spawn-Window "UPAS_DASHBOARD" @("-m", "tools.dashboard")
    Start-Sleep -Seconds 1

    Write-Host ""
    Write-Host "[launcher] CLI active below. Type 'help' for commands."
    Write-Host ""
    & $py -m tools.cli
}
finally {
    Write-Host ""
    Write-Host "[launcher] shutting down all child processes..."
    foreach ($p in $procs) {
        if ($p -and -not $p.HasExited) {
            try { taskkill /PID $p.Id /T /F 2>$null | Out-Null } catch {}
        }
    }
    # Kill any stray python running our modules
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" 2>$null |
        Where-Object { $_.CommandLine -match 'core\.scheduler|tools\.dashboard' } |
        ForEach-Object { try { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue } catch {} }
    Write-Host "[launcher] all stopped."
    Start-Sleep -Seconds 3
}
