"""
ai/scorer.py
Score 0–100: combine forward/reverse/meta signals with confidence weights.
Trigger question_router when uncertainty > threshold.
Return ranked signal list.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from config.variables import (
    AI_ENABLED,
    AI_MAX_CALLS_PER_CYCLE,
    AI_MIN_SCORE_FOR_API,
    ANTHROPIC_API_KEY,
    ANTHROPIC_MODEL_STANDARD,
    ANTHROPIC_TIER_A,
    ANTHROPIC_TIER_B,
    ANTHROPIC_TIER_C,
    CLAUDE_AUTH_MODE,
    UNCERTAINTY_THRESHOLD,
)
from logging_config.structured_logger import get_logger

logger = get_logger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tier_model(tier: str) -> str:
    """A=Opus (complex), B=Sonnet (standard), C=Haiku (bulk/cheap)."""
    return {"A": ANTHROPIC_TIER_A, "B": ANTHROPIC_TIER_B, "C": ANTHROPIC_TIER_C}.get(
        tier.upper(), ANTHROPIC_TIER_B
    )


def _call_claude(prompt: str, model: str | None = None, tier: str = "B") -> str:
    """
    Call Claude API, with local Ollama LLM as fallback.
    Routing:
      - LLM_LOCAL_ONLY=1 -> always local, never touch Claude
      - CLAUDE_AUTH_MODE=api + key set -> try Claude first, fallback to local
      - otherwise (user mode) -> try local directly
    Returns "" on complete failure.
    """
    if not AI_ENABLED:
        return ""

    from ai import local_llm

    # Fast path: local-only
    if local_llm.local_only():
        return local_llm.call(
            prompt, tier=tier,
            system=("You are a prediction market analyst. "
                    "When asked to rate a signal, reply with only an integer 0-100."),
        )

    effective_model = model or _tier_model(tier)

    if CLAUDE_AUTH_MODE.lower() == "api" and ANTHROPIC_API_KEY:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
            msg = client.messages.create(
                model=effective_model,
                max_tokens=16,
                system=[
                    {
                        "type": "text",
                        "text": (
                            "You are a prediction market analyst. "
                            "When asked to rate a signal, reply with only an integer 0-100."
                        ),
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[{"role": "user", "content": prompt}],
            )
            if msg.content:
                return msg.content[0].text
        except Exception as e:
            logger.warning("scorer.claude_api_error_fallback_local",
                           extra={"error": str(e)})

    # Local fallback — covers both "Claude failed" and "user mode without CLI"
    if local_llm.is_available():
        r = local_llm.call(
            prompt, tier=tier,
            system=("You are a prediction market analyst. "
                    "When asked to rate a signal, reply with only an integer 0-100."),
        )
        if r:
            logger.info("scorer.local_fallback_used", extra={"tier": tier})
            return r

    return ""


def score_signal(
    signal: dict[str, Any],
    reverse_validation: dict[str, Any] | None = None,
    meta_signals: list[dict[str, Any]] | None = None,
    allow_ai: bool = True,
) -> dict[str, Any]:
    """
    Score a single signal combining forward score, reverse validation, meta boost.

    Returns score record:
    {
        score_id, signal_id, ai_score, combined_score,
        confidence, model_used, timestamp
    }
    """
    base_score = signal.get("score", 0.0)
    confidence = signal.get("confidence", 0.5)
    uncertainty = signal.get("uncertainty", 0.3)
    direction = signal.get("direction", "forward")

    # ── Reverse validation penalty/bonus ────────────────────
    reverse_multiplier = 1.0
    if reverse_validation:
        if not reverse_validation.get("reverse_check_passed", True):
            reverse_score = reverse_validation.get("reverse_score", 0)
            reverse_multiplier = max(0.3, 1.0 - (reverse_score / 200))

    # ── Meta signal boost ────────────────────────────────────
    meta_boost = 0.0
    if meta_signals:
        for ms in meta_signals:
            if ms.get("market_id") == signal.get("market_id"):
                meta_boost = min(10.0, ms.get("score", 0) * 0.1)
                break

    # ── Direction weight ─────────────────────────────────────
    dir_weight = {"forward": 1.0, "reverse": 0.8, "meta": 0.9}.get(direction, 1.0)

    # ── Combined score ───────────────────────────────────────
    # Soft confidence weight [0.6, 1.0]: conf=0.6 → 0.84, conf=0.9 → 0.96.
    # Prevents strong signals with moderate confidence from being crushed below threshold.
    conf_weight = 0.6 + 0.4 * max(0.0, min(1.0, confidence))
    combined = (base_score * reverse_multiplier * dir_weight * conf_weight) + meta_boost
    combined = min(100.0, max(0.0, combined))

    # ── AI reasoning boost (if enabled + low uncertainty) ────
    ai_score = combined
    model_used = "rule_based"

    # Tier selection:
    #   A (Opus)  — contradicted / high-stakes (reverse failed) — deep reasoning
    #   B (Sonnet)— standard high-score signal
    #   C (Haiku) — borderline / bulk
    reverse_failed = bool(reverse_validation and not reverse_validation.get("reverse_check_passed", True))
    if reverse_failed and combined >= AI_MIN_SCORE_FOR_API:
        tier = "A"
    elif combined >= AI_MIN_SCORE_FOR_API:
        tier = "B"
    else:
        tier = "C"

    if (
        allow_ai
        and AI_ENABLED
        and CLAUDE_AUTH_MODE == "api"
        and uncertainty < UNCERTAINTY_THRESHOLD
        and combined >= AI_MIN_SCORE_FOR_API
    ):
        prompt = (
            f"Rate this prediction market signal 0-100.\n"
            f"Strategy: {signal.get('strategy_name')}\n"
            f"Direction: {direction}\n"
            f"Base score: {base_score:.1f}\n"
            f"Reasoning: {signal.get('reasoning', '')[:200]}\n"
            f"Confidence: {confidence:.2%}\n"
            f"Reverse check passed: {not reverse_failed}"
        )
        resp = _call_claude(prompt, tier=tier)
        try:
            ai_score = max(0.0, min(100.0, float(resp.strip())))
            combined = (combined + ai_score) / 2
            model_used = _tier_model(tier)
        except (ValueError, AttributeError):
            pass

    return {
        "score_id": str(uuid.uuid4()),
        "signal_id": signal.get("signal_id", ""),
        "ai_score": round(ai_score, 2),
        "combined_score": round(combined, 2),
        "confidence": round(confidence, 4),
        "model_used": model_used,
        "timestamp": _now(),
    }


def rank_signals(
    forward_signals: list[dict[str, Any]],
    reverse_validations: list[dict[str, Any]] | None = None,
    meta_signals: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """
    Score and rank all signals. Returns list sorted by combined_score descending.
    """
    val_map = {v["signal_id"]: v for v in (reverse_validations or [])}

    # Pre-rank by rule-based base score × confidence so AI budget goes to top signals
    prelim = sorted(
        forward_signals,
        key=lambda s: s.get("score", 0) * (0.6 + 0.4 * s.get("confidence", 0.5)),
        reverse=True,
    )
    ai_budget = AI_MAX_CALLS_PER_CYCLE if CLAUDE_AUTH_MODE == "api" else 0
    scored = []
    ai_calls = 0

    for sig in prelim:
        rv = val_map.get(sig.get("signal_id", ""))
        allow_ai = ai_calls < ai_budget
        score_rec = score_signal(sig, rv, meta_signals, allow_ai=allow_ai)
        if score_rec.get("model_used", "rule_based") != "rule_based":
            ai_calls += 1
        scored.append({**sig, **score_rec})

    scored.sort(key=lambda x: x.get("combined_score", 0), reverse=True)
    logger.info("scorer.ranked", extra={"total": len(scored), "ai_calls": ai_calls, "ai_budget": ai_budget})
    return scored
