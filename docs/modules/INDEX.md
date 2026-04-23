---
aliases: [Modules Index]
tags: [index, module]
type: index
related: [[HOME]], [[modules/ai]], [[modules/ml]], [[modules/rl]], [[modules/uncertainty-engine]], [[modules/assumption-guard]], [[modules/question-router]]
---

← [[HOME]]

# Modules Index

Core Python modules that power the system's intelligence layer.

| Module | File | Role |
|---|---|---|
| [[modules/ai]] | `ai/scorer.py`, `ai/reasoning.py` | Signal scoring and explanation |
| [[modules/ml]] | `ml/dataset.py`, `ml/features.py`, `ml/trainer.py` | XGBoost training pipeline |
| [[modules/rl]] | `rl/environment.py`, `rl/reward.py`, `rl/policy.py` | Reinforcement learning |
| [[modules/uncertainty-engine]] | `core/uncertainty_engine.py` | Confidence + uncertainty scoring |
| [[modules/assumption-guard]] | `core/assumption_guard.py` | Blast-radius estimation, inference blocking |
| [[modules/question-router]] | `core/question_router.py` | Pause pipeline, ask user, resume |

All modules are **optional by default** — the system works without AI/ML/RL enabled.
See [[config/settings]] for feature flags.
