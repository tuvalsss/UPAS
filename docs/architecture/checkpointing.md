---
aliases: [Checkpointing, Resumable Runs]
tags: [architecture, concept]
type: concept
related: [[HOME]], [[tools/checkpoint-tool]], [[pipeline/flow]], [[config/settings]], [[database/schema]]
---

← [[HOME]] → [[architecture/overview]]

# Checkpointing

## Purpose

UPAS supports **resumable runs**. Every pipeline stage saves its state so that if the process is interrupted (Ctrl+C, crash, power loss), it can resume from the last completed stage — not from scratch.

## How It Works

```
engine.py  →  checkpoint_tool.save(stage, state)  →  SQLite checkpoints table
                                                            ↓
cli/main.py replay  →  checkpoint_tool.load()  →  resume from stage
```

## Checkpoint Payload

```json
{
  "checkpoint_id": "uuid",
  "stage": "strategy | reverse | meta | score | store | alert",
  "pipeline_state": {},
  "markets_processed": [],
  "signals_generated": [],
  "timestamp": "ISO8601",
  "run_id": "uuid"
}
```

## Config

From [[config/settings]]:
- `checkpoint_interval: 300` — auto-checkpoint every 300 seconds in live mode

## CLI

```powershell
python cli/main.py status    # see last checkpoint
python cli/main.py replay    # resume from it
```

## Related

[[tools/checkpoint-tool]] · [[database/schema]] · [[pipeline/flow]] · [[cli/commands]]
