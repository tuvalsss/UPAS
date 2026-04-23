"""
core/strategy_scorecard.py
Per-strategy performance report derived from the `results` table.

- Called by CLI (`scorecard` command).
- Called by strategy_weights updater.
"""
from __future__ import annotations

from tools.database_tool import _conn


def scorecard() -> list[dict]:
    """Return per-strategy stats sorted by total_pnl desc."""
    with _conn() as con:
        rows = con.execute("""
            SELECT
              COALESCE(strategy_name, 'unknown') AS strategy,
              COUNT(*) AS n,
              SUM(CASE WHEN won=1 THEN 1 ELSE 0 END) AS wins,
              SUM(CASE WHEN won=0 THEN 1 ELSE 0 END) AS losses,
              ROUND(AVG(pnl_usd), 3) AS avg_pnl,
              ROUND(SUM(pnl_usd), 2) AS total_pnl
            FROM results
            WHERE pnl_usd IS NOT NULL
            GROUP BY strategy_name
            ORDER BY total_pnl DESC
        """).fetchall()

    cards = []
    for r in rows:
        strategy, n, wins, losses, avg_pnl, total_pnl = r
        win_rate = (wins / n) if n else 0.0
        cards.append({
            "strategy": strategy,
            "n": n,
            "wins": wins,
            "losses": losses,
            "win_rate": round(win_rate, 3),
            "avg_pnl_usd": avg_pnl or 0.0,
            "total_pnl_usd": total_pnl or 0.0,
        })
    return cards


def grand_total() -> dict:
    with _conn() as con:
        r = con.execute("""
            SELECT COUNT(*), SUM(CASE WHEN won=1 THEN 1 ELSE 0 END),
                   ROUND(SUM(pnl_usd), 2)
            FROM results WHERE pnl_usd IS NOT NULL
        """).fetchone()
    n, wins, total = r
    return {
        "trades": n or 0,
        "wins": wins or 0,
        "losses": (n or 0) - (wins or 0),
        "win_rate": round((wins or 0) / n, 3) if n else 0.0,
        "total_pnl_usd": total or 0.0,
    }


if __name__ == "__main__":
    import json
    print("GRAND TOTAL:", json.dumps(grand_total(), indent=2))
    print("\nPER STRATEGY:")
    for c in scorecard():
        print(f"  {c['strategy']:30s} n={c['n']:4d} W={c['wins']:3d}/L={c['losses']:3d} "
              f"wr={c['win_rate']*100:5.1f}% avg={c['avg_pnl_usd']:+.2f} total={c['total_pnl_usd']:+.2f}")
