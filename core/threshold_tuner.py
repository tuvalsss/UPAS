"""
core/threshold_tuner.py
Analyzes paper + real trade outcomes to suggest optimal MIN_SIGNAL_SCORE
and MIN_CONFIDENCE_EXEC thresholds.

Core idea: if signals with score=72 (currently below our 75 threshold)
consistently WIN in paper mode, our threshold is too conservative and
we're leaving edge on the table. If signals with score=80 LOSE as much
as score=70, our scoring is broken.

Output: human-readable report + structured suggestions. NEVER auto-applies.
The user decides when to tune env vars based on recommendations.

Usage:
  python -m core.threshold_tuner
  upas> tune
"""
from __future__ import annotations

from tools.database_tool import _conn


def bucket_performance(bucket_size: float = 5.0) -> list[dict]:
    """
    Group resolved trades (real + paper) by score bucket, report win rate + PnL.
    Use this to spot the 'sweet spot' where signals actually pay off.
    """
    with _conn() as con:
        rows = con.execute("""
            SELECT
              CAST(s.score / ? AS INTEGER) * ? AS bucket,
              COALESCE(r.paper_trade, 0) AS paper,
              COUNT(*) AS n,
              SUM(CASE WHEN r.won=1 THEN 1 ELSE 0 END) AS wins,
              ROUND(AVG(r.pnl_usd), 3) AS avg_pnl,
              ROUND(SUM(r.pnl_usd), 2) AS total_pnl
            FROM results r
            JOIN orders o ON o.order_id = r.signal_id
            JOIN signals s ON s.market_id = o.market_id
              AND s.timestamp <= o.timestamp
              AND s.timestamp >= datetime(o.timestamp, '-1 hour')
            WHERE r.pnl_usd IS NOT NULL
            GROUP BY bucket, paper
            ORDER BY bucket DESC
        """, (bucket_size, bucket_size)).fetchall()
    out = []
    for r in rows:
        bucket, paper, n, wins, avg_pnl, total_pnl = r
        out.append({
            "score_bucket": f"{int(bucket)}-{int(bucket+bucket_size)}",
            "bucket_low": int(bucket),
            "tier": "PAPER" if paper else "REAL",
            "n": n, "wins": wins, "losses": n - wins,
            "win_rate": round((wins / n), 3) if n else 0.0,
            "avg_pnl_usd": avg_pnl or 0.0,
            "total_pnl_usd": total_pnl or 0.0,
        })
    return out


def suggest_thresholds(min_samples: int = 10) -> dict:
    """
    Scan score buckets and find:
      - The LOWEST score bucket where win_rate >= 52% (profit-positive with typical prices)
      - The HIGHEST score bucket that's still losing money (ceiling)

    If paper data shows lower-tier wins consistently, suggest lowering
    MIN_SIGNAL_SCORE. If real trades lose even at high scores, suggest
    raising it.
    """
    buckets = bucket_performance(bucket_size=5.0)
    # Combine real + paper per bucket for total view
    combined: dict[int, dict] = {}
    for b in buckets:
        k = b["bucket_low"]
        c = combined.setdefault(k, {
            "score_bucket": b["score_bucket"], "bucket_low": k,
            "n": 0, "wins": 0, "losses": 0, "total_pnl_usd": 0.0,
        })
        c["n"] += b["n"]
        c["wins"] += b["wins"]
        c["losses"] += b["losses"]
        c["total_pnl_usd"] += b["total_pnl_usd"]
    for c in combined.values():
        c["win_rate"] = round(c["wins"] / c["n"], 3) if c["n"] else 0.0

    # Candidates for new threshold: lowest score where win_rate >= 52% and n >= min_samples
    sorted_b = sorted(combined.values(), key=lambda x: x["bucket_low"])
    suggested_min = None
    for b in sorted_b:
        if b["n"] >= min_samples and b["win_rate"] >= 0.52 and b["total_pnl_usd"] > 0:
            suggested_min = b["bucket_low"]
            break
    # Ceiling: highest bucket that still loses money
    high_loss = None
    for b in reversed(sorted_b):
        if b["n"] >= min_samples and b["total_pnl_usd"] < 0:
            high_loss = b["bucket_low"]
            break

    notes = []
    if suggested_min is not None:
        notes.append(
            f"Signals with score >= {suggested_min} have been profitable "
            f"({combined[suggested_min]['win_rate']*100:.0f}% WR on "
            f"{combined[suggested_min]['n']} trades). Consider lowering "
            f"MIN_SIGNAL_SCORE to {suggested_min}."
        )
    if high_loss is not None and (suggested_min is None or high_loss > suggested_min):
        notes.append(
            f"Signals even at score >= {high_loss} are losing money "
            f"({combined[high_loss]['total_pnl_usd']:+.2f} on "
            f"{combined[high_loss]['n']} trades). Strategy quality may be "
            f"broken at that tier — check per-strategy scorecard."
        )
    if not notes:
        notes.append(
            "Not enough resolved paper/real trades to make a threshold "
            f"recommendation (need n >= {min_samples} per bucket). "
            f"Let the bot run longer."
        )

    return {
        "buckets": sorted_b,
        "suggested_min_score": suggested_min,
        "highest_losing_bucket": high_loss,
        "notes": notes,
        "min_samples_per_bucket": min_samples,
    }


if __name__ == "__main__":
    import json
    s = suggest_thresholds()
    print("=== SCORE BUCKETS ===")
    for b in s["buckets"]:
        wr = b["win_rate"] * 100
        pnl = b["total_pnl_usd"]
        print(f"  score {b['score_bucket']:7s}  n={b['n']:4d}  "
              f"W={b['wins']:3d}/L={b['losses']:3d}  wr={wr:5.1f}%  "
              f"pnl=${pnl:+8.2f}")
    print()
    print("=== SUGGESTIONS ===")
    for note in s["notes"]:
        print(f"  * {note}")
    if s["suggested_min_score"]:
        print(f"\n  -> suggested MIN_SIGNAL_SCORE: {s['suggested_min_score']}")
