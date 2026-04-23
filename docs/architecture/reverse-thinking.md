---
aliases: [Reverse Thinking, Reverse-First, 5-Check Ritual]
tags: [architecture, concept]
type: concept
related: [[HOME]], [[architecture/overview]], [[architecture/uncertainty-model]], [[modules/assumption-guard]], [[modules/question-router]], [[modules/uncertainty-engine]]
---

← [[HOME]] → [[architecture/overview]]

# Reverse-Thinking System

## The Prime Directive

Before **any** file is created, tool written, or module built, execute the 5-check ritual:

| # | Question | Block if |
|---|---|---|
| 1 | Does this already exist? | Found in tools/packages/MCP/skills |
| 2 | Is the requirement fully clear? | Any ambiguity → ask user |
| 3 | More than one valid interpretation? | Present options, stop |
| 4 | What breaks if this assumption is wrong? | Blast radius is large |
| 5 | All checks pass? | Only then: proceed |

This directive **overrides every other instruction**.

## Reverse Validation Ritual

For every forward signal generated, [[strategies/reverse/INDEX]] runs its reverse counterpart:

```
forward_signal → reverse_validator → reverse_check_passed: bool
```

If `reverse_check_passed = false`, the signal is downgraded or discarded.

## Components

| Component | File | Role |
|---|---|---|
| Uncertainty Engine | `core/uncertainty_engine.py` | Score completeness, detect conflicts |
| Assumption Guard | `core/assumption_guard.py` | Intercept inferred values, estimate blast radius |
| Question Router | `core/question_router.py` | Ask user one direct question, pause pipeline |
| Reverse Validator | `reverse_strategies/reverse_validator.py` | Validate forward signals from opposite direction |

## Config Knobs

From [[config/settings]]:
- `ask_before_assuming: true` — block on any inference
- `uncertainty_threshold: 0.65` — below this, escalate to user
- `reverse_mode_enabled: true` — disable to skip reverse validation
- `fallback_to_user_question: true` — always ask if stuck

## Related

[[modules/uncertainty-engine]] · [[modules/assumption-guard]] · [[modules/question-router]] · [[strategies/reverse/INDEX]]
