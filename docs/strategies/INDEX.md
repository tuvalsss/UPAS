---
aliases: [Strategies Index]
tags: [index, strategy]
type: index
related: [[HOME]], [[strategies/core/INDEX]], [[strategies/reverse/INDEX]], [[strategies/meta/INDEX]], [[database/signal-schema]]
---

← [[HOME]]

# Strategies Index

Strategies are organized in three layers. Each strategy module implements `detect(market_data) -> List[Signal]`.

## Core Strategies — Forward Direction

[[strategies/core/INDEX]]

| Strategy | Signal Type | Key Indicator |
|---|---|---|
| [[strategies/core/yes-no-imbalance]] | forward | yes/no price gap > threshold |
| [[strategies/core/cross-market]] | forward | same event priced differently across platforms |
| [[strategies/core/time-decay]] | forward | probability shift as expiry approaches |
| [[strategies/core/panic-move]] | forward | sudden large price movement |
| [[strategies/core/high-prob-bond]] | forward | high-probability near-certain outcome |
| [[strategies/core/liquidity-shift]] | forward | significant liquidity redistribution |

## Reverse Strategies — Inversion Layer

[[strategies/reverse/INDEX]]

| Strategy | Reverse Signal | Threshold |
|---|---|---|
| [[strategies/reverse/probability-freeze]] | Suspiciously stable prob | 0.03 |
| [[strategies/reverse/liquidity-vacuum]] | Abnormally low liquidity | 200 |
| [[strategies/reverse/crowd-fatigue]] | Declining activity near event | 0.6 |
| [[strategies/reverse/whale-exhaustion]] | Large trader withdrawal | 0.8 |
| [[strategies/reverse/fake-momentum]] | Price without volume | 0.4 |
| [[strategies/reverse/event-shadow-drift]] | Correlated events drifting | 0.05 |
| [[strategies/reverse/mirror-event-divergence]] | Mirror events inconsistent | 0.1 |
| [[strategies/reverse/time-probability-inversion]] | Prob moving against time decay | 0.07 |

## Meta Strategies — Pattern Layer

[[strategies/meta/INDEX]]

| Strategy | Role |
|---|---|
| [[strategies/meta/opportunity-cluster]] | Correlated signal clusters |
| [[strategies/meta/signal-memory]] | Recurring pattern detection |
| [[strategies/meta/negative-signal-detector]] | Absence of expected signal |

## Signal Schema

See [[database/signal-schema]] for the standard signal object.

## Related

[[agents/strategy-agent]] · [[agents/reverse-strategy-agent]] · [[database/signal-schema]] · [[architecture/reverse-thinking]]
