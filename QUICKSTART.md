# UPAS — Quick Start Guide
## From zero to running in one command sequence

---

## Prerequisites

- **Python 3.10+** — https://python.org/downloads  
- **Git** — https://git-scm.com  
- **Claude Code CLI** — `npm install -g @anthropic-ai/claude-code` (for subagent features)

---

## Step 1 — Clone & enter the project

```powershell
cd C:\Users\tuval\GTproducts\UPAS
```

## Step 2 — Create virtual environment & install dependencies

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

> **PowerShell execution policy**: if you get a script-blocked error run once:
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```

## Step 3 — Verify credentials are in place

Your `.env` file and `config/kalshi_private_key.pem` are already populated.  
To confirm:

```powershell
python -c "from config.variables import settings_summary; import json; print(json.dumps(settings_summary(), indent=2))"
```

You should see all config values with no empty `database_path`.

## Step 4 — Initialize the system

```powershell
python cli/main.py init
```

This creates:
- `data/upas.db` — SQLite database with all 13 tables
- `data/checkpoints/` — checkpoint directory
- Tool registry snapshot in the database

## Step 5 — Run the doctor check

```powershell
python cli/main.py doctor
```

All checks should pass (✓). If any API check fails, verify your `.env` credentials.

## Step 6 — Run your first scan

```powershell
python cli/main.py scan --verbose
```

This runs one full pipeline pass:
`Scan → Normalize → Strategy → Reverse → Meta → Uncertainty → AI Score → Store → Alert → Checkpoint`

## Step 7 — See ranked signals

```powershell
python cli/main.py scan --json
```

Returns structured JSON with all signals scored and ranked.

## Step 8 — Start live continuous mode

```powershell
python cli/main.py live
```

Scans every 60 seconds (configurable in `config/settings.yaml`).  
Stop with **Ctrl+C** — state is checkpointed automatically.

## Step 9 — Resume after interrupt

```powershell
python cli/main.py replay
```

## Step 10 — Claude Code subagent mode (saves API credits)

```powershell
# Login with your Claude account (browser opens once)
claude login

# Run with user session instead of API key
python cli/main.py scan --verbose
# CLAUDE_AUTH_MODE=user in .env routes through CLI session
```

---

## All CLI Commands

| Command | What it does |
|---|---|
| `init` | Initialize DB, config, checkpoints, tool registry |
| `scan` | One full pipeline pass |
| `live` | Continuous mode (Ctrl+C to stop) |
| `analyze <id>` | Deep-dive on a market or signal by ID |
| `train` | Trigger XGBoost ML training on stored outcomes |
| `status` | Last checkpoint + system health |
| `replay` | Resume from last checkpoint |
| `export --format json` | Export signals to JSON/CSV |
| `backtest` | Run strategies against historical data |
| `doctor` | Verify environment + API connectivity |
| `ask "<question>"` | Submit clarification to the pipeline |
| `tools` | List all registered tools and their status |
| `explain <signal_id>` | Show full AI reasoning for a signal |

**Global flags:** `--json` `--verbose` `--strict` `--reverse`

---

## One-liner: full setup from scratch

```powershell
python -m venv .venv; .venv\Scripts\Activate.ps1; pip install -r requirements.txt; python cli/main.py init; python cli/main.py doctor; python cli/main.py scan --verbose
```

---

## Configuration

All settings live in **`config/settings.yaml`**.  
All secrets live in **`.env`** (never committed to git).

Key settings to tune:
- `scan_interval_seconds` — how often to scan in live mode
- `uncertainty_threshold` — below this confidence, system asks you before acting
- `reverse_mode_enabled` — set `false` to skip reverse strategy validation
- `claude_auth_mode` — `user` (CLI login, free) or `api` (ANTHROPIC_API_KEY)

---

## Obsidian Documentation Vault

Open the full interactive docs in Obsidian:

1. Install Obsidian → https://obsidian.md
2. Open Obsidian → **"Open folder as vault"** → select the `docs/` folder
3. Press **Ctrl+G** to open Graph View — see the entire system architecture
4. Start from `HOME.md`

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `ModuleNotFoundError` | Run `.venv\Scripts\Activate.ps1` then `pip install -r requirements.txt` |
| `API authentication error` | Check `.env` — ensure no trailing spaces on keys |
| `Kalshi key error` | Verify `config/kalshi_private_key.pem` exists |
| `Claude not found` | Run `npm install -g @anthropic-ai/claude-code` then `claude login` |
| `Database locked` | Kill other processes using `data/upas.db` |
| PowerShell script blocked | `Set-ExecutionPolicy RemoteSigned -Scope CurrentUser` |
