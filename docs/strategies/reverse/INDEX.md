---
aliases: [Reverse Strategies Index]
tags: [index, strategy]
type: index
related: [[strategies/INDEX]], [[architecture/reverse-thinking]], [[strategies/reverse/probability-freeze]], [[strategies/reverse/liquidity-vacuum]], [[strategies/reverse/crowd-fatigue]], [[strategies/reverse/whale-exhaustion]], [[strategies/reverse/fake-momentum]], [[strategies/reverse/event-shadow-drift]], [[strategies/reverse/mirror-event-divergence]], [[strategies/reverse/time-probability-inversion]]
---

← [[strategies/INDEX]]

# Reverse Strategies Index

Reverse strategies **validate forward signals from the opposite direction**. A forward signal that fails reverse validation is downgraded or discarded.

| Strategy | Threshold | File |
|---|---|---|
| [[strategies/reverse/probability-freeze]] | 0.03 | `strategies/reverse/probability_freeze.py` |
| [[strategies/reverse/liquidity-vacuum]] | 200 | `strategies/reverse/liquidity_vacuum.py` |
| [[strategies/reverse/crowd-fatigue]] | 0.6 | `strategies/reverse/crowd_fatigue.py` |
| [[strategies/reverse/whale-exhaustion]] | 0.8 | `strategies/reverse/whale_exhaustion.py` |
| [[strategies/reverse/fake-momentum]] | 0.4 | `strategies/reverse/fake_momentum.py` |
| [[strategies/reverse/event-shadow-drift]] | 0.05 | `strategies/reverse/event_shadow_drift.py` |
| [[strategies/reverse/mirror-event-divergence]] | 0.1 | `strategies/reverse/mirror_event_divergence.py` |
| [[strategies/reverse/time-probability-inversion]] | 0.07 | `strategies/reverse/time_probability_inversion.py` |

## How Reverse Validation Works

```
forward_signal
  → reverse_validator.validate(signal, market)
  → run matching reverse strategy
  → return reverse_check_passed: bool
```

See [[architecture/reverse-thinking]] and `reverse_strategies/reverse_validator.py`.
