"""
ml/dataset.py
Build training datasets from historical signals and outcomes.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from tools.database_tool import get_results_for_training, get_signals, get_signal_by_id, get_score_by_signal_id
from logging_config.structured_logger import get_logger

logger = get_logger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_training_records(min_outcomes: int = 50) -> list[dict[str, Any]]:
    """
    Join signals + scores + results into training records.
    Only includes records with realized outcomes.
    """
    results = get_results_for_training(min_count=min_outcomes)
    if len(results) < min_outcomes:
        logger.warning(
            "dataset.insufficient_outcomes",
            extra={"found": len(results), "required": min_outcomes},
        )
        return []

    records = []
    for res in results:
        signal_id = res.get("signal_id")
        sig = get_signal_by_id(signal_id) if signal_id else None
        if not sig:
            continue

        score_rec = get_score_by_signal_id(signal_id) or {}
        record = {
            "market_id": res.get("market_id", ""),
            "source": "",
            "strategy_signals": [sig] if sig.get("direction") != "reverse" else [],
            "reverse_signals": [sig] if sig.get("direction") == "reverse" else [],
            "meta_signals": [sig] if sig.get("direction") == "meta" else [],
            "ai_score": score_rec.get("ai_score", sig.get("score", 0.0)),
            "confidence": score_rec.get("confidence", sig.get("confidence", 0.5)),
            "uncertainty": sig.get("uncertainty", 0.3),
            "realized_outcome": res.get("realized_outcome"),
            "decision_path": sig.get("strategy_name", ""),
            "asked_user": False,
            "safe_inference": True,
            "timestamp": _now(),
        }
        records.append(record)

    logger.info("dataset.built", extra={"records": len(records)})
    return records


def get_dataset_stats() -> dict[str, Any]:
    """Return statistics about available training data."""
    results = get_results_for_training(min_count=0)
    resolved = [r for r in results if r.get("realized_outcome") is not None]
    correct = [r for r in resolved if r.get("realized_outcome") == 1]
    return {
        "total_results": len(results),
        "resolved": len(resolved),
        "correct": len(correct),
        "accuracy": len(correct) / max(len(resolved), 1),
    }
