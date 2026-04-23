---
aliases: [ML Agent, Machine Learning Agent]
tags: [agent]
type: agent
related: [[agents/INDEX]], [[agents/ai-uni]], [[modules/ml]], [[database/training-schema]], [[agents/data-agent]]
---

← [[agents/INDEX]]

# ml-agent

## Role

Builds training datasets from historical signals and outcomes, extracts features, triggers XGBoost model training, and logs structured training records.

## Tools Used

- [[tools/database-tool]] — read historical signals + outcomes
- `ml/dataset.py`, `ml/features.py`, `ml/trainer.py`

## Training Record Format

See [[database/training-schema]] for the full schema.

## File

`.claude/agents/ml-agent.md`

## Related

[[modules/ml]] · [[agents/rl-agent]] · [[database/training-schema]] · [[agents/data-agent]]
