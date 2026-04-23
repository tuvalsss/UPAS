---
aliases: [Signal Schema, Signal Object]
tags: [reference]
type: reference
related: [[database/schema]], [[database/market-schema]], [[strategies/INDEX]], [[agents/strategy-agent]], [[agents/reverse-strategy-agent]]
---

← [[database/schema]]

# Signal Schema — Standard Signal Object

All strategy outputs — core, reverse, and meta — conform to this schema.

## JSON Schema

```json
{
  "signal_id": "string",
  "market_id": "string",
  "strategy_name": "string",
  "direction": "forward | reverse | meta",
  "score": 0.0,
  "confidence": 0.0,
  "uncertainty": 0.0,
  "reasoning": "string",
  "suggested_action": "string",
  "timestamp": "ISO8601"
}
```

## Field Definitions

| Field | Type | Description |
|---|---|---|
| `signal_id` | UUID string | Unique signal identifier |
| `market_id` | string | FK → market object |
| `strategy_name` | string | e.g. `yes_no_imbalance`, `probability_freeze` |
| `direction` | enum | `forward`, `reverse`, or `meta` |
| `score` | float 0–100 | Raw strategy score before AI scoring |
| `confidence` | float 0–1 | How confident the strategy is |
| `uncertainty` | float 0–1 | How much the strategy doesn't know |
| `reasoning` | string | Human-readable explanation |
| `suggested_action` | string | e.g. `BUY YES`, `WATCH`, `AVOID` |
| `timestamp` | ISO8601 | When signal was generated |

## Reverse Validation Extension

After reverse validation, signals gain:
```json
{
  "reverse_check_passed": true,
  "reverse_score": 0.0,
  "reverse_reason": "string"
}
```

## Related

[[database/schema]] · [[database/market-schema]] · [[strategies/INDEX]] · [[agents/strategy-agent]]
