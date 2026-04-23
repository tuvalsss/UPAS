---
aliases: [Uncertainty Model, Confidence Scoring]
tags: [architecture, concept]
type: concept
related: [[HOME]], [[architecture/reverse-thinking]], [[modules/uncertainty-engine]], [[modules/assumption-guard]], [[modules/question-router]], [[config/settings]]
---

← [[HOME]] → [[architecture/overview]]

# Uncertainty Model

## Purpose

Every decision in UPAS carries a confidence score and an uncertainty score. When uncertainty is too high, the system **pauses and asks the user** rather than guessing.

## Scoring Schema

```json
{
  "confidence": 0.0,     // 0.0–1.0: how sure we are the signal is valid
  "uncertainty": 0.0,    // 0.0–1.0: how much we DON'T know
  "gaps": [],            // missing data fields
  "conflicts": []        // contradictory signals
}
```

`confidence + uncertainty` do not need to sum to 1.0. Both can be moderate simultaneously (partial knowledge with partial doubt).

## Threshold

From [[config/settings]]: `uncertainty_threshold: 0.65`

- `uncertainty < 0.65` → proceed normally
- `uncertainty ≥ 0.65` → route to [[modules/question-router]] → pause → ask user → resume

## Sources of Uncertainty

1. **Missing market data** — no volume, no expiry
2. **Conflicting signals** — forward says YES, reverse says NO
3. **Low liquidity** — price may not reflect true consensus
4. **New market** — no historical baseline
5. **API gaps** — partial response from Polymarket or Kalshi

## Components

[[modules/uncertainty-engine]] — computes the score  
[[modules/assumption-guard]] — blocks unsafe inferences  
[[modules/question-router]] — constructs and delivers the question  

## Audit Trail

Every uncertainty event is logged to `uncertainty_events` table (see [[database/schema]]) and `audit_logs`.
