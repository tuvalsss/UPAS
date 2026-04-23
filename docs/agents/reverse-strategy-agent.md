---
aliases: [Reverse Strategy Agent]
tags: [agent]
type: agent
related: [[agents/INDEX]], [[agents/ai-uni]], [[agents/strategy-agent]], [[strategies/reverse/INDEX]], [[architecture/reverse-thinking]], [[database/signal-schema]]
---

← [[agents/INDEX]]

# reverse-strategy-agent

## Role

Runs all **reverse strategies** against market data and validates every forward signal from the opposite direction. Returns `reverse_check_passed: bool` for each forward signal.

## Strategies Executed

[[strategies/reverse/probability-freeze]] · [[strategies/reverse/liquidity-vacuum]] · [[strategies/reverse/crowd-fatigue]] · [[strategies/reverse/whale-exhaustion]] · [[strategies/reverse/fake-momentum]] · [[strategies/reverse/event-shadow-drift]] · [[strategies/reverse/mirror-event-divergence]] · [[strategies/reverse/time-probability-inversion]]

## Output

- Reverse signal objects with `direction: "reverse"`
- Validation results: `{ signal_id, reverse_check_passed, reverse_score, reason }`

## File

`.claude/agents/reverse-strategy-agent.md`

## Related

[[strategies/reverse/INDEX]] · [[architecture/reverse-thinking]] · [[agents/strategy-agent]] · [[agents/uncertainty-agent]]
