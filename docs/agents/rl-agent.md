---
aliases: [RL Agent, Reinforcement Learning Agent]
tags: [agent]
type: agent
related: [[agents/INDEX]], [[agents/ai-uni]], [[modules/rl]], [[agents/ml-agent]], [[database/schema]]
---

← [[agents/INDEX]]

# rl-agent

## Role

Tracks signal outcomes, computes rewards based on prediction accuracy, manages policy experiments with rollback support.

## Responsibilities

- Track success/failure per strategy
- Reward by outcome (correct direction = positive reward)
- Track certainty vs uncertainty decisions
- Policy experiment history with rollback on negative performance

## Tools Used

- [[tools/database-tool]] — read `results` table
- `rl/environment.py`, `rl/reward.py`, `rl/policy.py`

## File

`.claude/agents/rl-agent.md`

## Related

[[modules/rl]] · [[agents/ml-agent]] · [[database/schema]]
