---
aliases: [System Overview, Architecture Overview]
tags: [architecture, concept]
type: concept
related: [[HOME]], [[pipeline/flow]], [[agents/INDEX]], [[tools/INDEX]], [[architecture/reverse-thinking]], [[architecture/uncertainty-model]]
---

← [[HOME]]

# System Architecture Overview

UPAS is a **modular, agent-driven prediction-market alpha-detection system** for Windows 10+.

## Core Design Principles

1. **Reverse-first** — run the [[architecture/reverse-thinking]] ritual before any new code
2. **Tool-reuse** — see [[architecture/tool-reuse-policy]] before building anything new
3. **Uncertainty-aware** — see [[architecture/uncertainty-model]] for confidence scoring
4. **Resumable** — every run is checkpointed; see [[architecture/checkpointing]]
5. **Windows-native** — no WSL required; see [[architecture/windows-requirements]]

## Layer Diagram

```
┌─────────────────────────────────────────────────┐
│                   CLI Layer                      │
│              cli/main.py (Click)                 │
└─────────────────┬───────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────┐
│              Orchestrator Agent                  │
│                  ai-uni                          │
└──┬──────────┬──────────┬──────────┬─────────────┘
   │          │          │          │
┌──▼──┐  ┌───▼──┐  ┌────▼──┐  ┌───▼────┐
│scan │  │strat │  │reverse│  │  data  │
│agent│  │agent │  │ agent │  │  agent │
└──┬──┘  └───┬──┘  └────┬──┘  └───┬────┘
   └──────────┴──────────┴──────────┘
                  │
┌─────────────────▼───────────────────────────────┐
│                  Tool Layer                      │
│  polymarket · kalshi · database · alert · mcp   │
│  checkpoint · uncertainty · registry · strategy  │
└─────────────────┬───────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────┐
│                 Core Engine                      │
│   Scan→Normalize→Strategy→Reverse→Meta→Score    │
└─────────────────────────────────────────────────┘
```

## Key Files

| Layer | File |
|---|---|
| Config | `config/settings.yaml`, `config/variables.py` |
| Engine | `core/engine.py`, `core/scheduler.py` |
| Uncertainty | `core/uncertainty_engine.py`, `core/assumption_guard.py` |
| AI Scoring | `ai/scorer.py`, `ai/reasoning.py` |
| ML | `ml/dataset.py`, `ml/features.py`, `ml/trainer.py` |
| RL | `rl/environment.py`, `rl/reward.py`, `rl/policy.py` |
| Database | `database/schema.py` |
| CLI | `cli/main.py` |

## Related

[[pipeline/flow]] · [[agents/ai-uni]] · [[modules/uncertainty-engine]] · [[database/schema]]
