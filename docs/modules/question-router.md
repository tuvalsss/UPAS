---
aliases: [Question Router, User Escalation]
tags: [module]
type: module
related: [[modules/INDEX]], [[modules/uncertainty-engine]], [[modules/assumption-guard]], [[architecture/reverse-thinking]], [[tools/checkpoint-tool]]
---

← [[modules/INDEX]]

# Question Router

**File**: `core/question_router.py`

## Purpose

When uncertainty is too high to proceed, constructs a single direct question, pauses the pipeline, saves a checkpoint, and waits for the user's answer before resuming.

## Protocol

```
1. uncertainty_engine detects uncertainty >= threshold
2. question_router.build_question(context) → one clear question
3. checkpoint_tool.save(current_stage, state)
4. Output question to console (and Telegram if configured)
5. Wait for user input via cli ask command or stdin
6. Resume pipeline from checkpoint with answer injected
```

## Question Format

```
[UPAS QUESTION]
Stage: strategy
Market: "Will the Fed raise rates in June?"
Issue: Forward signal says BUY YES but reverse strategy sees probability freeze.

Question: Should I treat this as a false signal and skip, or proceed with reduced confidence?

Answer (y/n/skip/detail):
```

## Logged To

- `questions_asked` table (append-only)
- `clarifications` table (with answer when received)

## Related

[[modules/uncertainty-engine]] · [[modules/assumption-guard]] · [[tools/checkpoint-tool]] · [[cli/commands]]
