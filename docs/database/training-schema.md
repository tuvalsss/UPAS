---
aliases: [Training Schema, ML Training Record]
tags: [reference]
type: reference
related: [[database/schema]], [[database/signal-schema]], [[modules/ml]], [[agents/ml-agent]]
---

← [[database/schema]]

# Training Schema — ML Training Record

Every pipeline run produces training records for XGBoost model training.

## JSON Schema

```json
{
  "market_id": "string",
  "source": "string",
  "strategy_signals": [],
  "reverse_signals": [],
  "meta_signals": [],
  "ai_score": 0.0,
  "confidence": 0.0,
  "uncertainty": 0.0,
  "realized_outcome": null,
  "decision_path": "string",
  "asked_user": false,
  "safe_inference": false,
  "timestamp": "ISO8601"
}
```

## Field Definitions

| Field | Type | Description |
|---|---|---|
| `market_id` | string | Market this record is for |
| `source` | string | `polymarket` or `kalshi` |
| `strategy_signals` | list | All forward signals for this market |
| `reverse_signals` | list | All reverse signals for this market |
| `meta_signals` | list | All meta signals for this market |
| `ai_score` | float 0–100 | Final AI-combined score |
| `confidence` | float 0–1 | Overall confidence at decision time |
| `uncertainty` | float 0–1 | Overall uncertainty at decision time |
| `realized_outcome` | int or null | `1=correct`, `0=wrong`, `null=pending` |
| `decision_path` | string | Which strategies contributed to decision |
| `asked_user` | bool | Did uncertainty engine ask a user question? |
| `safe_inference` | bool | Was this a safe inference (no user needed)? |
| `timestamp` | ISO8601 | When record was created |

## Related

[[database/schema]] · [[modules/ml]] · [[agents/ml-agent]] · [[modules/rl]]
