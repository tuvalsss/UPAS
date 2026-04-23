---
aliases: [AI Module, Scorer, Reasoning]
tags: [module]
type: module
related: [[modules/INDEX]], [[modules/uncertainty-engine]], [[modules/question-router]], [[database/signal-schema]], [[config/settings]]
---

← [[modules/INDEX]]

# AI Module

## Files
- `ai/scorer.py` — combines signals into a 0–100 score
- `ai/reasoning.py` — generates human-readable explanations

## Scorer

Combines forward, reverse, and meta signals with confidence weights:

```
combined_score = (
    forward_score * confidence_weight +
    reverse_score * (1 - reverse_penalty) +
    meta_score * meta_weight
) / normalizer
```

If `uncertainty > uncertainty_threshold`, triggers [[modules/question-router]].

Returns ranked list of signals sorted by `combined_score` descending.

## Reasoning

Generates two outputs per signal:
1. Human-readable string explaining why the signal exists (or should be ignored)
2. Structured object: `{ reason, evidence, counter_evidence, verdict }`

## Claude Integration

- `claude_auth_mode: user` → uses Claude Code CLI session (no API cost)
- `claude_auth_mode: api` → calls Anthropic API with `ANTHROPIC_API_KEY`
- Standard tasks use `claude-sonnet-4-5`
- Complex reasoning uses `claude-opus-4-5`

## Related

[[modules/uncertainty-engine]] · [[modules/question-router]] · [[database/signal-schema]] · [[config/settings]]
