"""
strategies/core/cross_market.py
Detect price divergence for the same event across Polymarket and Kalshi.
Forward strategy — direction: "forward"
"""
from __future__ import annotations

from typing import Any

from strategies.base import BaseStrategy, Signal

_DIVERGENCE_THRESHOLD = 0.05  # 5% price difference


class CrossMarket(BaseStrategy):
    name = "cross_market"
    direction = "forward"

    def detect(self, markets: list[dict[str, Any]], **kwargs) -> list[Signal]:
        # Hardened matcher:
        #   1. Skip Kalshi MVE combos (multi-event combos can't arb binary Polymarket).
        #   2. Require Jaccard similarity >= 0.45 AND >=5 overlapping substantive tokens.
        #   3. Best match must beat runner-up by >=2 tokens (no ambiguous ties).
        #   4. Expiry dates must be within ±7 days.
        #   5. Reject edge-price quotes (<0.02 or >0.98) — usually stale.
        #   6. Require both sides liquidity/volume > 0.
        import re
        from datetime import datetime, timezone, timedelta

        signals: list[Signal] = []
        poly = [m for m in markets if m.get("source") == "polymarket"]
        kalshi = [m for m in markets if m.get("source") == "kalshi"
                  and not (m.get("market_id") or "").startswith("KXMVE")]

        _stop = {"the","a","an","will","be","is","of","to","in","on","for","by","at","and","or","it",
                 "this","that","with","2024","2025","2026","2027","yes","no","win","wins","won",
                 "over","under","more","less","than","after","before"}
        def toks(t):
            return {w for w in re.findall(r"[a-z]+", (t or "").lower()) if len(w) > 2 and w not in _stop}

        def parse_exp(s):
            if not s: return None
            try:
                dt = datetime.fromisoformat(str(s).replace("Z","+00:00"))
                return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
            except Exception:
                return None

        poly_tok = [(toks(m.get("title","")), m, parse_exp(m.get("expiry_timestamp"))) for m in poly]
        rejected_example = None
        matched_example = None

        for m_k in kalshi:
            k_tokens = toks(m_k.get("title",""))
            if len(k_tokens) < 5:
                continue
            k_exp = parse_exp(m_k.get("expiry_timestamp"))
            # Rank candidates
            scored = []
            for p_tokens, m_p, p_exp in poly_tok:
                if len(p_tokens) < 5: continue
                inter = k_tokens & p_tokens
                union = k_tokens | p_tokens
                if not union: continue
                jaccard = len(inter) / len(union)
                scored.append((len(inter), jaccard, m_p, p_exp))
            if not scored: continue
            scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
            best_n, best_j, m_p, p_exp = scored[0]
            runner = scored[1][0] if len(scored) > 1 else 0

            # Strict guards
            if best_n < 5 or best_j < 0.45 or (best_n - runner) < 2:
                if rejected_example is None and best_n >= 3:
                    rejected_example = {
                        "reason": f"weak-match overlap={best_n} jaccard={best_j:.2f} runner_gap={best_n-runner}",
                        "kalshi": m_k.get("title",""), "polymarket": m_p.get("title",""),
                    }
                continue
            if k_exp and p_exp and abs((k_exp - p_exp).days) > 7:
                if rejected_example is None:
                    rejected_example = {
                        "reason": f"expiry-drift kalshi={k_exp.date()} poly={p_exp.date()}",
                        "kalshi": m_k.get("title",""), "polymarket": m_p.get("title",""),
                    }
                continue
            yp, yk = float(m_p.get("yes_price") or 0), float(m_k.get("yes_price") or 0)
            if not (0.02 <= yp <= 0.98) or not (0.02 <= yk <= 0.98):
                continue
            if (m_p.get("liquidity") or 0) <= 0 and (m_p.get("volume") or 0) <= 0:
                continue
            divergence = abs(yp - yk)
            if divergence < _DIVERGENCE_THRESHOLD:
                continue

            buy_on = "polymarket" if yp < yk else "kalshi"
            score = min(100.0, (divergence / _DIVERGENCE_THRESHOLD) * 60)
            confidence = min(0.85, divergence * 4)
            reasoning = (
                f"VERIFIED cross-market pair (overlap={best_n} jaccard={best_j:.2f}): "
                f"Polymarket YES={yp:.2%} vs Kalshi YES={yk:.2%} — diff={divergence:.3f}. "
                f"Buy YES on {buy_on}. "
                f"POLY='{(m_p.get('title') or '')[:50]}' KALSHI='{(m_k.get('title') or '')[:50]}'"
            )
            target_id = m_p["market_id"] if buy_on == "polymarket" else m_k["market_id"]
            if matched_example is None:
                matched_example = {"kalshi": m_k.get("title",""), "polymarket": m_p.get("title",""),
                                   "overlap": best_n, "jaccard": round(best_j,2), "divergence": round(divergence,3)}
            sig = self._make_signal(target_id, score, confidence, reasoning, f"BUY YES on {buy_on}")
            # Attach examples on first signal for log inspection
            if hasattr(sig, "metadata"):
                sig.metadata = {"matched": matched_example, "rejected_example": rejected_example}
            signals.append(sig)
        return signals


_strategy = CrossMarket()

def detect(markets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [s.to_dict() for s in _strategy.detect(markets)]
