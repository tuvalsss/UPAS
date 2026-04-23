---
aliases: [RL Module, Reinforcement Learning]
tags: [module]
type: module
related: [[modules/INDEX]], [[modules/ml]], [[agents/rl-agent]], [[database/schema]]
---

← [[modules/INDEX]]

# RL Module

**Files**: `rl/environment.py` · `rl/reward.py` · `rl/policy.py`

## Purpose

Learns which strategies produce the best outcomes over time using reinforcement learning with epsilon-greedy exploration.

## Components

### environment.py
Defines the prediction market environment:
- **State**: current market features + signal history
- **Actions**: which strategy weight combination to apply
- **Transitions**: based on observed market outcomes

### reward.py
Computes reward for each decision:
- Correct direction prediction → positive reward
- Wrong prediction → negative reward
- Uncertainty escalation that was correct → bonus reward
- Unnecessary user question → small penalty

### policy.py
Epsilon-greedy policy with decay:
- Exploration rate starts at 0.3, decays to 0.05
- Policy experiment tracking with rollback on negative performance
- Policy snapshots saved to `data/` and logged to `model_artifacts`

## CLI

```powershell
python cli/main.py train  # also updates RL policy
```

## Related

[[modules/ml]] · [[agents/rl-agent]] · [[database/schema]]
