---
aliases: [ML Module, Machine Learning]
tags: [module]
type: module
related: [[modules/INDEX]], [[modules/rl]], [[agents/ml-agent]], [[database/training-schema]]
---

← [[modules/INDEX]]

# ML Module

**Files**: `ml/dataset.py` · `ml/features.py` · `ml/trainer.py`

## Purpose

Trains XGBoost models on historical signal outcomes to improve future scoring accuracy.

## Pipeline

```
database (signals + results)
  → ml/dataset.py   → training DataFrame
  → ml/features.py  → feature matrix X, labels y
  → ml/trainer.py   → XGBoost fit → model artifact saved
```

## Features Extracted

- Signal scores (forward, reverse, meta)
- Confidence and uncertainty at decision time
- Market metadata (liquidity, volume, expiry proximity)
- Strategy combination patterns
- Whether user was asked (asked_user flag)

## Training Record

See [[database/training-schema]] for full schema.

## Model Output

Saved to `data/model_artifacts/` and logged to `model_artifacts` table.

## CLI

```powershell
python cli/main.py train --verbose
```

## Related

[[modules/rl]] · [[agents/ml-agent]] · [[database/training-schema]]
