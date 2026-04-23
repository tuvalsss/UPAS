---
aliases: [Uncertainty Engine]
tags: [module]
type: module
related: [[modules/INDEX]], [[modules/assumption-guard]], [[modules/question-router]], [[architecture/uncertainty-model]], [[agents/uncertainty-agent]]
---

← [[modules/INDEX]]

# Uncertainty Engine

**File**: `core/uncertainty_engine.py`

## Purpose

Scores every pipeline input for completeness and conflict, returning a structured uncertainty assessment.

## Output Schema

```json
{
  "confidence": 0.85,
  "uncertainty": 0.15,
  "gaps": ["missing volume field", "no expiry timestamp"],
  "conflicts": ["forward says BUY, reverse says AVOID"]
}
```

## Algorithm

1. Check all required market fields — missing = gap
2. Compare forward vs reverse signal directions — contradiction = conflict
3. Assess data recency — stale data lowers confidence
4. Score: `confidence = 1.0 - (gap_penalty + conflict_penalty + staleness_penalty)`

## Threshold

If `uncertainty >= uncertainty_threshold (0.65)` → [[modules/question-router]] is triggered.

## Related

[[modules/assumption-guard]] · [[modules/question-router]] · [[agents/uncertainty-agent]] · [[architecture/uncertainty-model]]
