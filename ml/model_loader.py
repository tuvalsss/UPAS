"""
ml/model_loader.py
Loads the trained XGBoost model if present; returns None otherwise.
AI scorer checks for this module and falls back to rule-based scoring when absent.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

_MODEL_PATH = Path(__file__).parent / "model.json"
_cached: Any = None


def load_model() -> Any | None:
    global _cached
    if _cached is not None:
        return _cached
    if not _MODEL_PATH.exists():
        return None
    try:
        import xgboost as xgb
        m = xgb.Booster()
        m.load_model(str(_MODEL_PATH))
        _cached = m
        return m
    except Exception:
        return None


def model_available() -> bool:
    return _MODEL_PATH.exists()
