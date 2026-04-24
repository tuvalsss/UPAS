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

## Runtime topology (5 windows)

```
┌─────────────────────────────────────────────────────────┐
│ UPAS MASTER  — foreground  — tools/cli.py REPL          │
│  closing this window tears down all children below      │
└─────────────────────────────────────────────────────────┘
   │ spawns on START_ALL.bat
   ├─► UPAS_SCHEDULER   core/scheduler.py  → run_pipeline() every 60s
   ├─► UPAS_DASHBOARD   tools/dashboard.py → live KPIs, positions, signals
   ├─► UPAS_MONITOR     core/position_monitor.py → SL/TP every 5 min
   └─► UPAS_TRACKER     core/outcome_tracker.py  → resolve outcomes + weights every 30 min
```

## Online pipeline (inside scheduler window)

See [[pipeline/flow]] for the full stage diagram. Summary:

`scan → normalize → strategies (core+meta, weighted) → reverse+validate → uncertainty → AI score → alert → execute (tier router: REAL / PAPER / DISCARD)`

Each stage emits a structured log event (`engine.<stage>.done`) and writes a checkpoint.

## Key Files

| Layer | File | State |
|---|---|---|
| Entry + loop | `START_ALL.bat`, `core/scheduler.py` | ✅ live |
| Pipeline | `core/engine.py::run_pipeline` | ✅ live |
| Scanners | `tools/polymarket_tool.py`, `tools/kalshi_tool.py`, `tools/chainlink_stream.py` | ✅ live |
| Strategies | `strategies/core/*`, `strategies/meta/*`, `strategies/reverse/*` | ✅ live |
| Reverse validator | `reverse_strategies/reverse_validator.py` | ✅ live |
| Uncertainty | `core/uncertainty_engine.py` | ✅ live (log-only, does not block) |
| AI scorer | `ai/scorer.py`, `ai/reasoning.py` | ✅ live |
| Sizing | `tools/sizing.py` (Kelly) + `core/compound_state.py` | ✅ live |
| Execution | `tools/execution_tool.py` (Poly + Kalshi) | ✅ live |
| Paper routing | `core/engine.py` (tier logic) + `tools/strategy_tool._PAPER_STRATEGIES` | ✅ live |
| Position monitor | `core/position_monitor.py` | ✅ live |
| Outcome tracker | `core/outcome_tracker.py` | ✅ live |
| Strategy scorecard | `core/strategy_scorecard.py` | ✅ live |
| Adaptive weights | `core/strategy_weights.py` | ✅ live |
| Threshold tuner | `core/threshold_tuner.py` | ✅ advisory |
| Wallet registry | `core/wallet_registry.py` | ✅ live (feeds smart_money) |
| Smart money strategy | `strategies/core/smart_money.py` | ✅ paper-only |
| ML re-ranker | `ml/reranker.py` | ⚠️ scaffold — trains at ≥100 outcomes |
| Strategy generator | `ai/strategy_generator.py` | ⚠️ scaffold — runs at ≥500 outcomes |
| License (optional) | `core/license_guard.py`, `tools/issue_license.py` | ⚠️ opt-in via `LICENSE_REQUIRED=1` |
| Database | `tools/database_tool.py`, `database/schema.py` | ✅ live |
| CLI | `tools/cli.py` (REPL) / `cli/main.py` (Click) | ✅ live |

**Not part of the live loop** (development / scaffolding only):
`.claude/agents/*`, `.claude/skills/*`, `core/question_router.py` (interactive mode), `tools/tool_discovery.py`, `rl/policy.py`.

## Related

[[pipeline/flow]] · [[agents/ai-uni]] · [[modules/uncertainty-engine]] · [[database/schema]]
