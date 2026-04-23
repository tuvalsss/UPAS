---
aliases: [UPAS Home, Vault Index]
tags: [index]
type: index
related: [[architecture/overview]], [[agents/INDEX]], [[tools/INDEX]], [[strategies/INDEX]], [[modules/INDEX]], [[database/schema]], [[cli/commands]], [[obsidian-setup/guide]]
---

# 🏠 UPAS — Universal Prediction Alpha System

> *Reverse-first · uncertainty-aware · Windows-native · never duplicates*

Welcome to the UPAS Obsidian vault. Every component of the system is documented here with dense [[wikilinks]] — open **Graph View** (Ctrl+G) to see the full architecture map.

---

## 🗺️ System Map

```
ai-uni (orchestrator)
  ├── scanner-agent       → Polymarket + Kalshi
  ├── strategy-agent      → core + meta strategies
  ├── reverse-strategy-agent → reverse validation
  ├── data-agent          → storage + dedup
  ├── ml-agent            → XGBoost training
  ├── rl-agent            → reward + policy
  ├── reviewer-agent      → quality + drift
  ├── uncertainty-agent   → ambiguity detection
  └── tool-discovery-agent → reuse before build
```

---

## 📚 Documentation Index

### Current state
→ [[STATUS]] — live snapshot, profitability model, gaps, CTO priorities

### Architecture
→ [[architecture/overview]] · [[architecture/reverse-thinking]] · [[architecture/uncertainty-model]] · [[architecture/tool-reuse-policy]] · [[architecture/checkpointing]] · [[architecture/windows-requirements]]

### Pipeline
→ [[pipeline/flow]] · [[pipeline/scheduler]]

### Agents
→ [[agents/INDEX]] · [[agents/ai-uni]] · [[agents/scanner-agent]] · [[agents/strategy-agent]] · [[agents/reverse-strategy-agent]] · [[agents/data-agent]] · [[agents/ml-agent]] · [[agents/rl-agent]] · [[agents/reviewer-agent]] · [[agents/uncertainty-agent]] · [[agents/tool-discovery-agent]]

### Tools
→ [[tools/INDEX]] · [[tools/polymarket-tool]] · [[tools/kalshi-tool]] · [[tools/database-tool]] · [[tools/alert-tool]] · [[tools/strategy-tool]] · [[tools/mcp-bridge]] · [[tools/npm-bridge]] · [[tools/checkpoint-tool]] · [[tools/uncertainty-tool]] · [[tools/tool-registry]] · [[tools/tool-discovery]]

### Strategies
→ [[strategies/INDEX]]
- **Core**: [[strategies/core/yes-no-imbalance]] · [[strategies/core/cross-market]] · [[strategies/core/time-decay]] · [[strategies/core/panic-move]] · [[strategies/core/high-prob-bond]] · [[strategies/core/liquidity-shift]]
- **Reverse**: [[strategies/reverse/probability-freeze]] · [[strategies/reverse/liquidity-vacuum]] · [[strategies/reverse/crowd-fatigue]] · [[strategies/reverse/whale-exhaustion]] · [[strategies/reverse/fake-momentum]] · [[strategies/reverse/event-shadow-drift]] · [[strategies/reverse/mirror-event-divergence]] · [[strategies/reverse/time-probability-inversion]]
- **Meta**: [[strategies/meta/opportunity-cluster]] · [[strategies/meta/signal-memory]] · [[strategies/meta/negative-signal-detector]]

### Modules
→ [[modules/INDEX]] · [[modules/ai]] · [[modules/ml]] · [[modules/rl]] · [[modules/uncertainty-engine]] · [[modules/assumption-guard]] · [[modules/question-router]]

### Database
→ [[database/schema]] · [[database/market-schema]] · [[database/signal-schema]] · [[database/training-schema]]

### Config
→ [[config/settings]] · [[config/variables]]

### CLI
→ [[cli/commands]]

### Setup
→ [[obsidian-setup/guide]]

---

## ⚡ Pipeline at a Glance

`Scan → Normalize → Strategy → Reverse → Meta → Uncertainty → AI Score → Store → Alert → Checkpoint`

See [[pipeline/flow]] for the full diagram.

---

## 🔑 Prime Directive

Before any file is created or tool is built, run the **5-check reverse ritual** (see [[architecture/reverse-thinking]]):
1. Does this already exist?
2. Is the requirement fully clear?
3. Is there more than one valid interpretation?
4. What breaks if this assumption is wrong?
5. Only then: proceed.
