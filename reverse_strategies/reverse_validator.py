"""
reverse_strategies/reverse_validator.py
Run every forward signal through its reverse counterpart.
Returns reverse_check_passed: bool for each signal.
"""
from __future__ import annotations

import importlib
from typing import Any

from logging_config.structured_logger import get_logger

logger = get_logger(__name__)

# Maps forward strategy → reverse strategies that should validate it
_FORWARD_TO_REVERSE: dict[str, list[str]] = {
    "yes_no_imbalance":    ["probability_freeze", "fake_momentum", "liquidity_vacuum"],
    "cross_market":        ["mirror_event_divergence", "event_shadow_drift"],
    "time_decay":          ["time_probability_inversion", "crowd_fatigue"],
    "panic_move":          ["fake_momentum", "whale_exhaustion"],
    "high_prob_bond":      ["probability_freeze", "time_probability_inversion"],
    "liquidity_shift":     ["whale_exhaustion", "fake_momentum", "liquidity_vacuum"],
}


def _run_reverse_strategy(name: str, markets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Load and run a reverse strategy module."""
    try:
        mod = importlib.import_module(f"strategies.reverse.{name}")
        return mod.detect(markets)
    except Exception as e:
        logger.error("reverse_validator.strategy_error", extra={"strategy": name, "error": str(e)})
        return []


def validate(
    forward_signal: dict[str, Any],
    markets: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Validate a single forward signal against its reverse counterparts.

    Returns:
        {
            signal_id: str,
            reverse_check_passed: bool,
            reverse_score: float,
            reverse_reason: str,
            contradicting_strategies: List[str]
        }
    """
    strategy_name = forward_signal.get("strategy_name", "")
    market_id = forward_signal.get("market_id", "")
    signal_id = forward_signal.get("signal_id", "")

    reverse_names = _FORWARD_TO_REVERSE.get(strategy_name, [
        "liquidity_vacuum", "probability_freeze"  # defaults
    ])

    contradictions: list[str] = []
    reverse_scores: list[float] = []

    # Find the specific market
    target_markets = [m for m in markets if m.get("market_id") == market_id]
    if not target_markets:
        return {
            "signal_id": signal_id,
            "reverse_check_passed": True,
            "reverse_score": 0.0,
            "reverse_reason": "Market not found for reverse check — passing by default",
            "contradicting_strategies": [],
        }

    for rev_name in reverse_names:
        rev_signals = _run_reverse_strategy(rev_name, target_markets)
        for rev_sig in rev_signals:
            if rev_sig.get("market_id") == market_id:
                rev_score = rev_sig.get("score", 0.0)
                reverse_scores.append(rev_score)
                if rev_score > 50.0:  # Significant reverse signal
                    contradictions.append(rev_name)

    avg_reverse = sum(reverse_scores) / len(reverse_scores) if reverse_scores else 0.0
    reverse_check_passed = len(contradictions) < len(reverse_names)

    reason = (
        f"Reverse check: {len(contradictions)}/{len(reverse_names)} reverse strategies fired. "
        f"Avg reverse score: {avg_reverse:.1f}. "
        + (f"Contradictions: {', '.join(contradictions)}" if contradictions else "No contradictions.")
    )

    logger.info(
        "reverse_validator.result",
        extra={
            "signal_id": signal_id,
            "passed": reverse_check_passed,
            "contradictions": len(contradictions),
        },
    )

    return {
        "signal_id": signal_id,
        "reverse_check_passed": reverse_check_passed,
        "reverse_score": avg_reverse,
        "reverse_reason": reason,
        "contradicting_strategies": contradictions,
    }


def validate_all(
    forward_signals: list[dict[str, Any]],
    markets: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Validate all forward signals. Returns list of validation results."""
    results = []
    for sig in forward_signals:
        result = validate(sig, markets)
        results.append(result)
    return results
