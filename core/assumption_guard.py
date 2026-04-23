"""
core/assumption_guard.py
Intercept inferred values, evaluate blast radius, block if ask_before_assuming=true.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from config.variables import ASK_BEFORE_ASSUMING
from tools.database_tool import append_audit_log
from logging_config.structured_logger import get_logger

logger = get_logger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _estimate_blast_radius(
    inferred_value: str,
    context: dict[str, Any],
) -> str:
    """
    Estimate blast radius if the inference is wrong.
    Returns: "LOW" | "MEDIUM" | "HIGH"
    """
    signals_affected = len(context.get("signals", []))
    stores_to_db = context.get("writes_to_db", False)
    affects_score = context.get("affects_scoring", False)

    if stores_to_db or affects_score:
        return "HIGH"
    if signals_affected > 5:
        return "MEDIUM"
    return "LOW"


def guard(
    inferred_value: str,
    actual_value: Any,
    context: dict[str, Any] | None = None,
    on_block: Callable | None = None,
) -> tuple[Any, bool]:
    """
    Guard an inferred value.

    Args:
        inferred_value: human-readable description of what's being inferred
        actual_value: the value that would be used if not blocked
        context: surrounding context (signals, db writes, etc.)
        on_block: callback if inference is blocked

    Returns:
        (value, was_blocked): value = actual_value if allowed, None if blocked
    """
    context = context or {}
    blast = _estimate_blast_radius(inferred_value, context)
    blocked = False

    if ASK_BEFORE_ASSUMING and blast in ("HIGH", "MEDIUM"):
        blocked = True
        logger.warning(
            "assumption_guard.blocked",
            extra={
                "inferred": inferred_value,
                "blast_radius": blast,
                "ask_before_assuming": ASK_BEFORE_ASSUMING,
            },
        )
        try:
            append_audit_log(
                action="assumption_blocked",
                actor="assumption_guard",
                details={
                    "inferred_value": inferred_value,
                    "blast_radius": blast,
                    "blocked": True,
                    "timestamp": _now(),
                },
            )
        except Exception:
            pass

        if on_block:
            on_block(inferred_value, blast, context)

        return None, True

    # LOW blast radius or ask_before_assuming=False — allow with log
    logger.debug(
        "assumption_guard.allowed",
        extra={"inferred": inferred_value, "blast_radius": blast},
    )
    return actual_value, False
