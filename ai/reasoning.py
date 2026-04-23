"""
ai/reasoning.py
Generate human-readable explanations for signals.
Returns structured reasoning object.
"""
from __future__ import annotations

from typing import Any

from config.variables import AI_ENABLED, ANTHROPIC_MODEL_COMPLEX, CLAUDE_AUTH_MODE
from logging_config.structured_logger import get_logger

logger = get_logger(__name__)


def explain(
    signal: dict[str, Any],
    market: dict[str, Any] | None = None,
    reverse_validation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Generate reasoning for a signal.

    Returns:
    {
        summary: str,                  # one-line human-readable
        evidence: List[str],           # supporting evidence
        counter_evidence: List[str],   # why it might be wrong
        verdict: str,                  # STRONG | MODERATE | WEAK | DISCARD
        confidence_narrative: str
    }
    """
    strategy = signal.get("strategy_name", "unknown")
    direction = signal.get("direction", "forward")
    score = signal.get("combined_score", signal.get("score", 0))
    confidence = signal.get("confidence", 0.5)
    base_reasoning = signal.get("reasoning", "")
    suggested_action = signal.get("suggested_action", "WATCH")

    # Evidence from signal
    evidence = [base_reasoning] if base_reasoning else []

    # Counter evidence from reverse validation
    counter = []
    if reverse_validation:
        if not reverse_validation.get("reverse_check_passed", True):
            counter.append(f"Reverse check FAILED: {reverse_validation.get('reverse_reason', '')}")
            for cs in reverse_validation.get("contradicting_strategies", []):
                counter.append(f"Contradicted by: {cs}")
        else:
            evidence.append(f"Reverse check passed: {reverse_validation.get('reverse_reason', '')}")

    # Market context
    if market:
        evidence.append(
            f"Market: {market.get('title', '')[:60]} "
            f"[{market.get('source', '')}] "
            f"YES={market.get('yes_price', 0):.2%} "
            f"Liq=${market.get('liquidity', 0):.0f}"
        )

    # Verdict
    if score >= 75 and not counter:
        verdict = "STRONG"
    elif score >= 55 and len(counter) < 2:
        verdict = "MODERATE"
    elif score >= 35:
        verdict = "WEAK"
    else:
        verdict = "DISCARD"

    summary = (
        f"{direction.upper()} signal from {strategy} — "
        f"score={score:.1f}, action={suggested_action}, verdict={verdict}"
    )

    confidence_narrative = (
        f"Confidence {confidence:.0%}: "
        + ("High confidence — proceed." if confidence > 0.75
           else "Moderate confidence — proceed with caution." if confidence > 0.50
           else "Low confidence — consider asking for input.")
    )

    result = {
        "summary": summary,
        "evidence": evidence,
        "counter_evidence": counter,
        "verdict": verdict,
        "confidence_narrative": confidence_narrative,
    }

    logger.debug("reasoning.explain", extra={"verdict": verdict, "strategy": strategy})
    return result
