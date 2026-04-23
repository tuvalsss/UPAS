---
aliases: [Scheduler, Continuous Mode]
tags: [architecture, concept]
type: concept
related: [[HOME]], [[pipeline/flow]], [[architecture/checkpointing]], [[config/settings]], [[cli/commands]]
---

← [[HOME]] → [[pipeline/flow]]

# Scheduler

## Purpose

`core/scheduler.py` manages **continuous mode** — running the pipeline repeatedly on a configurable interval with Windows-safe process control.

## Behaviour

1. Run pipeline pass
2. Save checkpoint
3. Wait `scan_interval_seconds` (default: 60)
4. Exponential backoff on consecutive errors (max 10 min)
5. Graceful shutdown on Ctrl+C — checkpoint saved before exit

## Backoff Strategy

```
attempt 1: wait 60s
attempt 2: wait 120s
attempt 3: wait 240s
attempt 4: wait 480s
attempt 5+: wait 600s (cap)
```

## Windows Ctrl+C Handling

```python
import signal, sys

def _shutdown(sig, frame):
    checkpoint_tool.save("shutdown", current_state)
    sys.exit(0)

signal.signal(signal.SIGINT, _shutdown)
```

## Config

From [[config/settings]]:
- `scan_interval_seconds: 60`
- `checkpoint_interval: 300`

## CLI

```powershell
python cli/main.py live           # start continuous mode
python cli/main.py live --reverse # run uncertainty checks first each pass
```

## Related

[[pipeline/flow]] · [[tools/checkpoint-tool]] · [[cli/commands]] · [[architecture/checkpointing]]
