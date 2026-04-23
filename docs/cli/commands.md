---
aliases: [CLI Commands, Commands Reference]
tags: [reference, config]
type: reference
related: [[HOME]], [[config/settings]], [[pipeline/flow]], [[architecture/checkpointing]]
---

← [[HOME]]

# CLI Commands Reference

All commands: `python cli/main.py <command> [flags]`

## Commands

| Command | Purpose |
|---|---|
| `init` | Initialize database, config, checkpoints, tool registry |
| `scan` | Run one full pipeline pass |
| `live` | Start continuous mode (Ctrl+C to stop safely) |
| `analyze <id>` | Deep-dive analysis of a market or signal by ID |
| `train` | Trigger XGBoost ML training on stored outcomes |
| `status` | Show last checkpoint + system health |
| `replay` | Resume pipeline from last checkpoint |
| `export` | Export signals to JSON or CSV |
| `backtest` | Run strategies against historical data |
| `doctor` | Verify environment, dependencies, API connectivity |
| `ask "<question>"` | Submit a clarification directly to the pipeline |
| `tools` | List all registered tools and their status |
| `explain <signal_id>` | Show full AI reasoning for a signal |

## Global Flags

| Flag | Effect |
|---|---|
| `--json` | Output as structured JSON |
| `--verbose` | Show detailed step-by-step logs |
| `--strict` | Force ask-before-assuming on every inference |
| `--reverse` | Run uncertainty checks first before each stage |

## Examples

```powershell
# First run
python cli/main.py init

# Single scan with JSON output
python cli/main.py scan --json

# Continuous mode, verbose
python cli/main.py live --verbose

# Check what happened
python cli/main.py status

# Resume after interrupt
python cli/main.py replay

# Train model
python cli/main.py train --verbose

# Export last 100 signals
python cli/main.py export --format json --limit 100

# Run doctor check
python cli/main.py doctor

# Explain a specific signal
python cli/main.py explain abc123-signal-id
```

## Related

[[pipeline/flow]] · [[architecture/checkpointing]] · [[config/settings]]
