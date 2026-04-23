"""
core/uncertainty_engine.py
Score data completeness, detect conflicts, return uncertainty assessment.
This is the central component of the reverse-thinking system.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from config.variables import UNCERTAINTY_THRESHOLD

_REQUIRED_MARKET_FIELDS = [
    "market_id", "title", "source", "yes_price", "no_price",
    "liquidity", "expiry_timestamp", "fetched_at",
]


def score(
    market: dict[str, Any],
    signals: list[dict[str, Any]] | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Assess confidence and uncertainty for a market + its signals.

    Returns:
        {
            confidence: float,      # 0.0–1.0
            uncertainty: float,     # 0.0–1.0
            gaps: List[str],        # missing required fields
            conflicts: List[str],   # contradicting signals
            assumptions: List[dict],
            safe_to_proceed: bool
        }
    """
    signals = signals or []
    context = context or {}

    gaps: list[str] = []
    conflicts: list[str] = []
    assumptions: list[dict[str, Any]] = []

    # ── 1. Field completeness ────────────────────────────────
    for field in _REQUIRED_MARKET_FIELDS:
        val = market.get(field)
        if val is None or val == "" or val == 0.0:
            gaps.append(f"missing_or_zero: {field}")

    # ── 2. Price sanity checks ───────────────────────────────
    yes = market.get("yes_price", -1)
    no = market.get("no_price", -1)
    if yes < 0 or yes > 1:
        gaps.append("yes_price out of range [0,1]")
    if no < 0 or no > 1:
        gaps.append("no_price out of range [0,1]")
    if yes >= 0 and no >= 0 and abs((yes + no) - 1.0) > 0.15:
        conflicts.append(f"yes+no={yes+no:.3f} — significant deviation from 1.0")
        # Inferred assumption
        assumptions.append({
            "value": f"no_price inferred as 1 - yes_price",
            "blast_radius": "LOW",
            "safe": True,
        })

    # ── 3. Data staleness ────────────────────────────────────
    fetched_at = market.get("fetched_at", "")
    if fetched_at:
        try:
            fetched = datetime.fromisoformat(fetched_at.replace("Z", "+00:00"))
            age_minutes = (datetime.now(timezone.utc) - fetched).total_seconds() / 60
            if age_minutes > 30:
                gaps.append(f"stale_data: fetched {age_minutes:.0f} min ago")
        except Exception:
            gaps.append("unparseable fetched_at timestamp")

    # ── 4. Signal conflict detection ─────────────────────────
    forward_sigs = [s for s in signals if s.get("direction") == "forward"]
    reverse_sigs = [s for s in signals if s.get("direction") == "reverse"]

    if forward_sigs and reverse_sigs:
        fwd_actions = {s.get("suggested_action", "") for s in forward_sigs}
        rev_actions = {s.get("suggested_action", "") for s in reverse_sigs}
        if "BUY YES" in fwd_actions and "AVOID" in rev_actions:
            conflicts.append("forward=BUY_YES conflicts with reverse=AVOID")
        if "BUY NO" in fwd_actions and "BUY YES" in rev_actions:
            conflicts.append("forward=BUY_NO conflicts with reverse=BUY_YES")

    # ── 5. Score calculation ─────────────────────────────────
    gap_penalty = min(0.5, len(gaps) * 0.08)
    conflict_penalty = min(0.4, len(conflicts) * 0.15)
    confidence = max(0.0, 1.0 - gap_penalty - conflict_penalty)
    uncertainty = min(1.0, gap_penalty + conflict_penalty)

    safe_to_proceed = uncertainty < UNCERTAINTY_THRESHOLD

    return {
        "confidence": round(confidence, 4),
        "uncertainty": round(uncertainty, 4),
        "gaps": gaps,
        "conflicts": conflicts,
        "assumptions": assumptions,
        "safe_to_proceed": safe_to_proceed,
    }
