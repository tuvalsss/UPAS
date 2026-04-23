---
aliases: [Config Variables, Python Config]
tags: [config, reference]
type: reference
related: [[config/settings]], [[HOME]]
---

← [[config/settings]]

# Config Variables

`config/variables.py` is the **Python-importable mirror** of `config/settings.yaml`.

Every module imports from here. Never hardcode a value anywhere else.

## Usage

```python
from config.variables import SCAN_INTERVAL_SECONDS, UNCERTAINTY_THRESHOLD

# Use directly
if uncertainty > UNCERTAINTY_THRESHOLD:
    question_router.ask(...)
```

## Key Constants

| Constant | Source Key |
|---|---|
| `CAPITAL` | `capital` |
| `RISK_PER_TRADE` | `risk_per_trade` |
| `SCAN_INTERVAL_SECONDS` | `scan_interval_seconds` |
| `UNCERTAINTY_THRESHOLD` | `uncertainty_threshold` |
| `CLAUDE_AUTH_MODE` | env `CLAUDE_AUTH_MODE` → yaml `claude_auth_mode` |
| `ANTHROPIC_MODEL_STANDARD` | env → yaml |
| `ANTHROPIC_MODEL_COMPLEX` | env → yaml |
| `DATABASE_PATH` | env `DATABASE_PATH` → yaml `database_path` |
| `POLY_API_KEY` | env `POLY_API_KEY` |
| `KALSHI_PRIVATE_KEY_PATH` | env `KALSHI_PRIVATE_KEY_PATH` |

## Priority

`environment variable` overrides `settings.yaml` value — allows per-environment overrides without editing the yaml file.

## Related

[[config/settings]] · [[architecture/overview]]
