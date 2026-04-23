---
aliases: [Strategy Agent]
tags: [agent]
type: agent
related: [[agents/INDEX]], [[agents/ai-uni]], [[strategies/INDEX]], [[strategies/core/INDEX]], [[strategies/meta/INDEX]], [[tools/strategy-tool]], [[database/signal-schema]]
---

← [[agents/INDEX]]

# strategy-agent

## Role

Executes all **core** and **meta** strategies against normalized market data, returns standardized signal objects.

## Strategies Executed

**Core**: [[strategies/core/yes-no-imbalance]] · [[strategies/core/cross-market]] · [[strategies/core/time-decay]] · [[strategies/core/panic-move]] · [[strategies/core/high-prob-bond]] · [[strategies/core/liquidity-shift]]

**Meta**: [[strategies/meta/opportunity-cluster]] · [[strategies/meta/signal-memory]] · [[strategies/meta/negative-signal-detector]]

## Tools Used

- [[tools/strategy-tool]] — strategy registry and dispatcher

## Output

List of signal objects with `direction: "forward" | "meta"`. See [[database/signal-schema]].

## File

`.claude/agents/strategy-agent.md`

## Related

[[agents/reverse-strategy-agent]] · [[strategies/INDEX]] · [[database/signal-schema]]
