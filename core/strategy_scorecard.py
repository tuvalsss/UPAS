"""
core/strategy_scorecard.py
Per-strategy performance report derived from the `results` table.

- Called by CLI (`scorecard` command).
- Called by strategy_weights updater.
"""
from __future__ import annotations

from tools.database_tool import _conn


def _ensure_paper_column():
    """Ensure results.paper_trade exists (idempotent). Called on module import
    so scorecard queries never fail on an un-migrated DB."""
    try:
        with _conn() as con:
            existing = {r[1] for r in con.execute("PRAGMA table_info(results)").fetchall()}
            if "paper_trade" not in existing:
                con.execute("ALTER TABLE results ADD COLUMN paper_trade INTEGER")
                con.commit()
    except Exception:
        pass


_ensure_paper_column()


def scorecard() -> list[dict]:
    """
    Return per-strategy stats sorted by total_pnl desc.
    Paper-traded strategies are reported separately — their rows have
    strategy labelled as '<name> [paper]' so it's obvious they are not
    realized cash gains/losses.
    """
    with _conn() as con:
        rows = con.execute("""
            SELECT
              COALESCE(strategy_name, 'unknown') AS strategy,
              COALESCE(paper_trade, 0) AS paper,
              COUNT(*) AS n,
              SUM(CASE WHEN won=1 THEN 1 ELSE 0 END) AS wins,
              SUM(CASE WHEN won=0 THEN 1 ELSE 0 END) AS losses,
              ROUND(AVG(pnl_usd), 3) AS avg_pnl,
              ROUND(SUM(pnl_usd), 2) AS total_pnl
            FROM results
            WHERE pnl_usd IS NOT NULL
            GROUP BY strategy_name, paper_trade
            ORDER BY total_pnl DESC
        """).fetchall()

    cards = []
    for r in rows:
        strategy, paper, n, wins, losses, avg_pnl, total_pnl = r
        label = f"{strategy} [paper]" if paper else strategy
        win_rate = (wins / n) if n else 0.0
        cards.append({
            "strategy": label,
            "is_paper": bool(paper),
            "raw_strategy": strategy,
            "n": n, "wins": wins, "losses": losses,
            "win_rate": round(win_rate, 3),
            "avg_pnl_usd": avg_pnl or 0.0,
            "total_pnl_usd": total_pnl or 0.0,
        })
    return cards


def grand_total() -> dict:
    """Grand total covers REAL trades only. Paper trades separate via paper_total()."""
    with _conn() as con:
        r = con.execute("""
            SELECT COUNT(*), SUM(CASE WHEN won=1 THEN 1 ELSE 0 END),
                   ROUND(SUM(pnl_usd), 2)
            FROM results
            WHERE pnl_usd IS NOT NULL AND COALESCE(paper_trade, 0) = 0
        """).fetchone()
    n, wins, total = r
    return {
        "trades": n or 0,
        "wins": wins or 0,
        "losses": (n or 0) - (wins or 0),
        "win_rate": round((wins or 0) / n, 3) if n else 0.0,
        "total_pnl_usd": total or 0.0,
    }


def paper_total() -> dict:
    """Paper-only results (would-be PnL if strategy were live)."""
    with _conn() as con:
        r = con.execute("""
            SELECT COUNT(*), SUM(CASE WHEN won=1 THEN 1 ELSE 0 END),
                   ROUND(SUM(pnl_usd), 2)
            FROM results
            WHERE pnl_usd IS NOT NULL AND paper_trade = 1
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
