---
aliases: [Assumption Guard, Blast Radius]
tags: [module]
type: module
related: [[modules/INDEX]], [[modules/uncertainty-engine]], [[modules/question-router]], [[architecture/reverse-thinking]], [[database/schema]]
---

← [[modules/INDEX]]

# Assumption Guard

**File**: `core/assumption_guard.py`

## Purpose

Intercepts any inferred value before it is used. If `ask_before_assuming: true`, blocks execution and routes to [[modules/question-router]].

## Blast Radius Estimation

For each inference, estimates what breaks if the assumption is wrong:

| Blast Radius | Action |
|---|---|
| LOW — affects only one signal | Allow with warning logged |
| MEDIUM — affects multiple signals | Require confirmation |
| HIGH — affects stored data or decisions | Block, ask user |

## Audit Trail

Every interception logged to `audit_logs` table with:
```json
{
  "inferred_value": "...",
  "blast_radius": "HIGH",
  "blocked": true,
  "question_asked": true
}
```

## Config

`ask_before_assuming: true` in [[config/settings]] — enables full blocking mode.

## Related

[[modules/uncertainty-engine]] · [[modules/question-router]] · [[architecture/reverse-thinking]] · [[database/schema]]
