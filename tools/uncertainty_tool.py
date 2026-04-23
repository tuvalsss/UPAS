"""
tools/uncertainty_tool.py
Exposes uncertainty engine functions as a reusable tool interface.
"""
from __future__ import annotations

from typing import Any

from core.uncertainty_engine import score as _score_uncertainty
from logging_config.structured_logger import get_logger

logger = get_logger(__name__)


def assess(
    market: dict[str, Any] | None = None,
    signals: list[dict[str, Any]] | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Run uncertainty assessment on market data + signals.
    Returns: { confidence, uncertainty, gaps, conflicts, safe_to_proceed }
    """
    result = _score_uncertainty(
        market=market or {},
        signals=signals or [],
        context=context or {},
    )
    logger.info(
        "uncertainty_tool.assess",
        extra={
            "confidence": result.get("confidence"),
            "uncertainty": result.get("uncertainty"),
            "safe_to_proceed": result.get("safe_to_proceed"),
        },
    )
    return result


def is_safe(assessment: dict[str, Any]) -> bool:
    """Quick helper: True if the assessment says it's safe to proceed."""
    return assessment.get("safe_to_proceed", False)
