"""
strategies/core/cross_market_ai.py
AI-assisted fuzzy matching layer on top of cross_market.py.

Produces candidate Poly/Kalshi pairs with LOOSER token overlap
(Jaccard 0.25 or overlap >=3), then asks Claude to verify whether the
pair describes the same real-world event. Verdicts are cached in
`market_pair_cache` to bound AI cost (one call per unique pair ever).

Budget: hard cap AI_CALLS_PER_CYCLE (default 20). Everything else is cached.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Any

from logging_config.structured_logger import get_logger
from strategies.base import BaseStrategy, Signal
from tools.database_tool import _conn

logger = get_logger(__name__)

_MIN_OVERLAP = 3
_MAX_OVERLAP_AUTO = 5           # >=5 is already handled by strict cross_market
_JACCARD_MIN = 0.25
_JACCARD_AUTO = 0.45
_DIVERGENCE_THRESHOLD = 0.05
_AI_CALLS_PER_CYCLE = int(os.getenv("CROSS_MARKET_AI_BUDGET", "20"))
_CACHE_VALID_DAYS = 14

_STOP = {
    "the","a","an","will","be","is","of","to","in","on","for","by","at","and","or","it",
    "this","that","with","2024","2025","2026","2027","yes","no","win","wins","won",
    "over","under","more","less","than","after","before",
}


def _toks(t: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]+", (t or "").lower()) if len(w) > 2 and w not in _STOP}


def _parse_exp(s):
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
    except Exception:
        return None


def _cache_get(poly_id: str, kalshi_id: str) -> dict | None:
    with _conn() as con:
        r = con.execute(
            "SELECT verdict, confidence, reason, created_at FROM market_pair_cache "
            "WHERE poly_id=? AND kalshi_id=?", (poly_id, kalshi_id),
        ).fetchone()
    if not r:
        return None
    try:
        created = datetime.fromisoformat(r["created_at"])
        if (datetime.now(timezone.utc) - created).days > _CACHE_VALID_DAYS:
            return None
    except Exception:
        pass
    return {"verdict": r["verdict"], "confidence": r["confidence"], "reason": r["reason"]}


def _cache_put(poly_id: str, kalshi_id: str, verdict: str, confidence: float, reason: str):
    with _conn() as con:
        con.execute(
            "INSERT OR REPLACE INTO market_pair_cache "
            "(poly_id, kalshi_id, verdict, confidence, reason, created_at) VALUES (?,?,?,?,?,?)",
            (poly_id, kalshi_id, verdict, float(confidence), reason[:300],
             datetime.now(timezone.utc).isoformat()),
        )


def _ai_verify_pair(poly_title: str, kalshi_title: str) -> dict:
    """Ask Claude if the two titles describe the same real-world event.
    Returns {verdict: 'match'|'mismatch'|'ambiguous', confidence: 0..1, reason: str}.
    """
    from ai.scorer import _call_claude

    prompt = (
        "You are verifying whether two prediction-market titles describe the "
        "EXACT SAME real-world event with binary YES/NO resolution.\n\n"
        f"Polymarket: {poly_title}\n"
        f"Kalshi:     {kalshi_title}\n\n"
        "Criteria for MATCH:\n"
        " - Same subject (same person/team/asset/event)\n"
        " - Same condition (same threshold/outcome)\n"
        " - Same resolution window (same date or event)\n"
        " - A YES on one = YES on the other (no inverted logic)\n\n"
        "Respond with STRICT JSON only (no prose, no markdown), shape:\n"
        '{"verdict":"match"|"mismatch"|"ambiguous","confidence":0.0-1.0,"reason":"short"}\n'
    )
    try:
        resp = _call_claude(prompt, tier="B")
    except Exception as e:
        return {"verdict": "ambiguous", "confidence": 0.0, "reason": f"ai_error:{e}"}

    raw = (resp or "").strip()
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return {"verdict": "ambiguous", "confidence": 0.0, "reason": f"unparsed:{raw[:80]}"}
    try:
        data = json.loads(m.group(0))
    except Exception:
        return {"verdict": "ambiguous", "confidence": 0.0, "reason": f"json_err:{raw[:80]}"}
    v = str(data.get("verdict", "ambiguous")).lower()
    if v not in ("match", "mismatch", "ambiguous"):
        v = "ambiguous"
    try:
        conf = float(data.get("confidence", 0.0))
    except Exception:
        conf = 0.0
    reason = str(data.get("reason", ""))[:280]
    return {"verdict": v, "confidence": max(0.0, min(1.0, conf)), "reason": reason}


class CrossMarketAI(BaseStrategy):
    name = "cross_market_ai"
    direction = "forward"

    def detect(self, markets: list[dict[str, Any]], **kwargs) -> list[Signal]:
        signals: list[Signal] = []
        poly = [m for m in markets if m.get("source") == "polymarket"]
        kalshi = [m for m in markets
                  if m.get("source") == "kalshi"
                  and not (m.get("market_id") or "").startswith("KXMVE")]

        poly_enriched = [(_toks(m.get("title", "")), m, _parse_exp(m.get("expiry_timestamp"))) for m in poly]

        ai_calls_remaining = _AI_CALLS_PER_CYCLE
        cache_hits = 0
        new_matches = 0

        # Pre-rank all candidates globally so we spend AI budget on best ones first.
        candidates: list[tuple[int, float, dict, dict]] = []
        for m_k in kalshi:
            k_tokens = _toks(m_k.get("title", ""))
            if len(k_tokens) < 3:
                continue
            k_exp = _parse_exp(m_k.get("expiry_timestamp"))
            scored = []
            for p_tokens, m_p, p_exp in poly_enriched:
                if len(p_tokens) < 3:
                    continue
                inter = k_tokens & p_tokens
                union = k_tokens | p_tokens
                if not union:
                    continue
                n = len(inter)
                j = n / len(union)
                if n < _MIN_OVERLAP or j < _JACCARD_MIN:
                    continue
                # Expiry sanity check: within 14d or unknown
                if k_exp and p_exp and abs((k_exp - p_exp).days) > 14:
                    continue
                # Skip if strict cross_market already picks this up (auto-accept)
                if n >= _MAX_OVERLAP_AUTO and j >= _JACCARD_AUTO:
                    continue
                # Skip edge prices
                yp = float(m_p.get("yes_price") or 0)
                yk = float(m_k.get("yes_price") or 0)
                if not (0.02 <= yp <= 0.98) or not (0.02 <= yk <= 0.98):
                    continue
                if abs(yp - yk) < _DIVERGENCE_THRESHOLD:
                    continue  # no tradable divergence
                scored.append((n, j, m_p, m_k))
            if scored:
                # keep top candidate per Kalshi market only
                scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
                candidates.append(scored[0])

        # Sort globally by divergence × jaccard (high-value first for AI budget)
        def cand_priority(c):
            n, j, m_p, m_k = c
            yp = float(m_p.get("yes_price") or 0)
            yk = float(m_k.get("yes_price") or 0)
            div = abs(yp - yk)
            return (div * j, n)

        candidates.sort(key=cand_priority, reverse=True)

        for n, j, m_p, m_k in candidates:
            poly_id = m_p["market_id"]
            kalshi_id = m_k["market_id"]
            cached = _cache_get(poly_id, kalshi_id)
            if cached:
                cache_hits += 1
                verdict = cached["verdict"]
                conf = cached["confidence"]
                reason = cached["reason"]
            else:
                if ai_calls_remaining <= 0:
                    continue
                ai_calls_remaining -= 1
                res = _ai_verify_pair(m_p.get("title", ""), m_k.get("title", ""))
                verdict, conf, reason = res["verdict"], res["confidence"], res["reason"]
                _cache_put(poly_id, kalshi_id, verdict, conf, reason)

            if verdict != "match" or conf < 0.70:
                continue

            yp = float(m_p.get("yes_price") or 0)
            yk = float(m_k.get("yes_price") or 0)
            divergence = abs(yp - yk)
            buy_on = "polymarket" if yp < yk else "kalshi"
            target_id = m_p["market_id"] if buy_on == "polymarket" else m_k["market_id"]
            score = min(100.0, (divergence / _DIVERGENCE_THRESHOLD) * 55 + conf * 20)
            confidence = min(0.90, 0.45 + divergence * 3 + (conf - 0.7) * 0.8)
            reasoning = (
                f"AI-VERIFIED cross-market (overlap={n} jaccard={j:.2f} ai_conf={conf:.2f}): "
                f"Poly YES={yp:.2%} vs Kalshi YES={yk:.2%} diff={divergence:.3f}. "
                f"Buy YES on {buy_on}. AI_reason: {reason[:100]}"
            )
            signals.append(self._make_signal(target_id, score, confidence, reasoning, f"BUY YES on {buy_on}"))
            new_matches += 1

        logger.info("cross_market_ai.run", extra={
            "candidates": len(candidates),
            "cache_hits": cache_hits,
            "ai_calls_used": _AI_CALLS_PER_CYCLE - ai_calls_remaining,
            "signals_out": new_matches,
        })
        return signals


_strategy = CrossMarketAI()


def detect(markets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [s.to_dict() for s in _strategy.detect(markets)]
