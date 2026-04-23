"""
ml/features.py
Feature extraction from market data, signals, and metadata for XGBoost training.
"""
from __future__ import annotations

from typing import Any

import numpy as np


_CORE_STRATEGIES = [
    "yes_no_imbalance", "cross_market", "time_decay",
    "panic_move", "high_prob_bond", "liquidity_shift",
]
_REVERSE_STRATEGIES = [
    "probability_freeze", "liquidity_vacuum", "crowd_fatigue",
    "whale_exhaustion", "fake_momentum", "event_shadow_drift",
    "mirror_event_divergence", "time_probability_inversion",
]
_META_STRATEGIES = [
    "opportunity_cluster", "signal_memory", "negative_signal_detector",
]


def extract(record: dict[str, Any]) -> dict[str, float]:
    """
    Extract feature vector from a training record.
    Returns flat dict of float features.
    """
    features: dict[str, float] = {}

    # ── Forward signal features ──────────────────────────────
    fwd = record.get("strategy_signals", [])
    for name in _CORE_STRATEGIES:
        sig = next((s for s in fwd if s.get("strategy_name") == name), None)
        features[f"fwd_{name}_score"] = sig.get("score", 0.0) if sig else 0.0
        features[f"fwd_{name}_conf"] = sig.get("confidence", 0.0) if sig else 0.0
        features[f"fwd_{name}_fired"] = 1.0 if sig else 0.0

    # ── Reverse signal features ───────────────────────────────
    rev = record.get("reverse_signals", [])
    for name in _REVERSE_STRATEGIES:
        sig = next((s for s in rev if s.get("strategy_name") == name), None)
        features[f"rev_{name}_score"] = sig.get("score", 0.0) if sig else 0.0
        features[f"rev_{name}_fired"] = 1.0 if sig else 0.0

    # ── Meta signal features ──────────────────────────────────
    meta = record.get("meta_signals", [])
    for name in _META_STRATEGIES:
        sig = next((s for s in meta if s.get("strategy_name") == name), None)
        features[f"meta_{name}_score"] = sig.get("score", 0.0) if sig else 0.0
        features[f"meta_{name}_fired"] = 1.0 if sig else 0.0

    # ── Aggregate signal features ────────────────────────────
    all_fwd_scores = [s.get("score", 0) for s in fwd]
    all_rev_scores = [s.get("score", 0) for s in rev]

    features["fwd_count"] = float(len(fwd))
    features["rev_count"] = float(len(rev))
    features["meta_count"] = float(len(meta))
    features["fwd_avg_score"] = float(np.mean(all_fwd_scores)) if all_fwd_scores else 0.0
    features["rev_avg_score"] = float(np.mean(all_rev_scores)) if all_rev_scores else 0.0
    features["fwd_rev_ratio"] = len(fwd) / max(len(rev), 1)

    # ── AI scoring features ───────────────────────────────────
    features["ai_score"] = float(record.get("ai_score", 0.0))
    features["confidence"] = float(record.get("confidence", 0.5))
    features["uncertainty"] = float(record.get("uncertainty", 0.3))

    # ── Uncertainty / decision features ──────────────────────
    features["asked_user"] = 1.0 if record.get("asked_user") else 0.0
    features["safe_inference"] = 1.0 if record.get("safe_inference") else 0.0

    return features


def build_feature_matrix(records: list[dict[str, Any]]) -> tuple:
    """
    Build X (features) and y (labels) from training records.
    Returns (X: np.ndarray, y: np.ndarray, feature_names: List[str])
    """
    if not records:
        return np.array([]), np.array([]), []

    feature_dicts = [extract(r) for r in records]
    feature_names = list(feature_dicts[0].keys())

    X = np.array([[fd.get(k, 0.0) for k in feature_names] for fd in feature_dicts])
    y = np.array([float(r.get("realized_outcome", 0) or 0) for r in records])

    return X, y, feature_names
