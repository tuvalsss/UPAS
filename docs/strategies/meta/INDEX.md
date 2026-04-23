---
aliases: [Meta Strategies Index]
tags: [index, strategy]
type: index
related: [[strategies/INDEX]], [[strategies/meta/opportunity-cluster]], [[strategies/meta/signal-memory]], [[strategies/meta/negative-signal-detector]]
---

← [[strategies/INDEX]]

# Meta Strategies Index

Meta strategies operate on **aggregated signal data** — they detect patterns across strategies, not individual markets.

| Strategy | Role | File |
|---|---|---|
| [[strategies/meta/opportunity-cluster]] | Correlated signal clusters | `strategies/meta/opportunity_cluster.py` |
| [[strategies/meta/signal-memory]] | Recurring pattern detection | `strategies/meta/signal_memory.py` |
| [[strategies/meta/negative-signal-detector]] | Absence of expected signal | `strategies/meta/negative_signal_detector.py` |

Meta signals have `direction: "meta"` in the signal schema. See [[database/signal-schema]].
