"""
tools/dashboard.py
Live terminal dashboard for UPAS. 2s refresh via rich.Live.
Read-only — never places orders.

Run: python -m tools.dashboard
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.layout import Layout
from rich.text import Text

from tools.account_tool import get_polymarket_account, get_kalshi_balance
from tools.database_tool import _conn, get_recent_orders
from config.variables import DRY_RUN, AUTO_EXECUTE, MIN_SIGNAL_SCORE, MIN_CONFIDENCE_EXEC, CLAUDE_AUTH_MODE

_ROOT = Path(__file__).parent.parent
_LOG_FILE = _ROOT / "logs" / "upas.jsonl"
_ML_MODEL = _ROOT / "ml" / "model.json"


def _ago(ts: str | None) -> str:
    if not ts:
        return "—"
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        s = (datetime.now(timezone.utc) - dt).total_seconds()
        if s < 60: return f"{int(s)}s"
        if s < 3600: return f"{int(s/60)}m"
        return f"{int(s/3600)}h"
    except Exception:
        return ts[:16]


def _fetch_state() -> dict:
    st: dict = {}
    try:
        p = get_polymarket_account()
        st["poly_cash"] = p.get("cash_balance_usd", 0)
        st["poly_pos"] = p.get("positions_value_usd", 0)
        st["poly_total"] = p.get("total_value_usd", 0)
        st["poly_open"] = p.get("open_orders", 0)
        st["poly_err"] = None
    except Exception as e:
        st["poly_cash"] = st["poly_pos"] = st["poly_total"] = 0
        st["poly_err"] = str(e)[:50]
    try:
        k = get_kalshi_balance()
        if k.get("error"):
            # API down — reuse last known if available
            st["k_cash"] = getattr(_panel_state, "_last_k_cash", None)
            st["k_pos"] = getattr(_panel_state, "_last_k_pos", None)
            st["k_total"] = getattr(_panel_state, "_last_k_total", None)
            st["k_err"] = f"API: {str(k['error'])[:60]}"
        else:
            st["k_cash"] = k.get("cash_balance_usd", 0)
            st["k_pos"] = k.get("portfolio_value_usd", 0)
            st["k_total"] = k.get("total_value_usd", 0)
            st["k_err"] = None
            _fetch_state._last_k_cash = st["k_cash"]
            _fetch_state._last_k_pos = st["k_pos"]
            _fetch_state._last_k_total = st["k_total"]
    except Exception as e:
        st["k_cash"] = getattr(_panel_state, "_last_k_cash", None)
        st["k_pos"] = getattr(_panel_state, "_last_k_pos", None)
        st["k_total"] = getattr(_panel_state, "_last_k_total", None)
        st["k_err"] = str(e)[:60]

    with _conn() as con:
        st["mk_poly"] = con.execute("SELECT COUNT(*), MAX(fetched_at) FROM markets WHERE source='polymarket'").fetchone()
        st["mk_kalshi"] = con.execute("SELECT COUNT(*), MAX(fetched_at) FROM markets WHERE source='kalshi'").fetchone()
        st["sig_10m"] = con.execute("SELECT COUNT(*) FROM signals WHERE timestamp >= datetime('now','-10 minutes')").fetchone()[0]
        st["sig_24h"] = con.execute("SELECT COUNT(*) FROM signals WHERE timestamp >= datetime('now','-1 day')").fetchone()[0]
        st["arb"] = con.execute(
            "SELECT COUNT(*) FROM signals WHERE strategy_name='cross_market' AND timestamp>=datetime('now','-1 day')"
        ).fetchone()[0]
        st["arb_sample"] = con.execute(
            """SELECT s.market_id, s.score, m.title FROM signals s LEFT JOIN markets m ON s.market_id=m.market_id
               WHERE s.strategy_name='cross_market' ORDER BY s.timestamp DESC LIMIT 3"""
        ).fetchall()
        st["positions"] = con.execute(
            "SELECT exchange, market_id, side, size_contracts, exposure_usd FROM positions WHERE size_contracts>0 ORDER BY exposure_usd DESC LIMIT 8"
        ).fetchall()
        st["positions_total"] = con.execute(
            "SELECT COUNT(*) FROM positions WHERE size_contracts>0"
        ).fetchone()[0]
        st["last_trade"] = con.execute(
            """SELECT timestamp, exchange, side, price, size_usd, status, market_id FROM orders
               WHERE dry_run=0 ORDER BY timestamp DESC LIMIT 1"""
        ).fetchone()
        st["orders_live"] = con.execute("SELECT COUNT(*) FROM orders WHERE dry_run=0 AND timestamp>=datetime('now','-1 day')").fetchone()[0]
        st["orders_dry"] = con.execute("SELECT COUNT(*) FROM orders WHERE dry_run=1 AND timestamp>=datetime('now','-1 day')").fetchone()[0]
        st["last_cp"] = con.execute("SELECT stage, timestamp FROM checkpoints ORDER BY timestamp DESC LIMIT 1").fetchone()
        st["strat_24h"] = con.execute(
            """SELECT strategy_name, COUNT(*) c, AVG(score) sc FROM signals
               WHERE timestamp>=datetime('now','-1 day') GROUP BY strategy_name ORDER BY c DESC"""
        ).fetchall()
        st["top_sig"] = con.execute(
            """SELECT s.strategy_name, s.direction, sc.combined_score, sc.confidence, s.market_id, m.title, m.yes_price, m.source
               FROM signals s JOIN scores sc ON s.signal_id=sc.signal_id
               LEFT JOIN markets m ON s.market_id=m.market_id
               WHERE s.timestamp>=datetime('now','-10 minutes')
               ORDER BY sc.combined_score DESC LIMIT 5"""
        ).fetchall()

    # Error count from log tail
    st["err_1h"] = 0
    try:
        if _LOG_FILE.exists():
            import json as _j
            cutoff = datetime.now(timezone.utc).timestamp() - 3600
            with open(_LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
                try:
                    f.seek(max(0, os.path.getsize(_LOG_FILE) - 500_000))
                    f.readline()
                except Exception:
                    pass
                for line in f:
                    try:
                        e = _j.loads(line)
                        if e.get("level") in ("ERROR", "CRITICAL"):
                            ts = datetime.fromisoformat(e["timestamp"].replace("Z", "+00:00")).timestamp()
                            if ts >= cutoff:
                                st["err_1h"] += 1
                    except Exception:
                        continue
    except Exception:
        pass

    st["ml_loaded"] = _ML_MODEL.exists()
    try:
        from rl.policy import EpsilonGreedyPolicy  # noqa
        st["rl_ok"] = True
    except Exception:
        st["rl_ok"] = False
    return st


def _render(st: dict) -> Panel:
    mode = "[bold red]LIVE[/]" if (AUTO_EXECUTE and not DRY_RUN) else "[bold green]DRY[/]"
    now = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
    header = Text.from_markup(
        f"  UPAS DASHBOARD   mode={mode}   refresh=2s   {now}   "
        f"thresholds score≥{MIN_SIGNAL_SCORE} conf≥{MIN_CONFIDENCE_EXEC}"
    )

    # ─── 12 KPI panel ───
    kpi = Table.grid(padding=(0, 2))
    kpi.add_column(style="bold cyan"); kpi.add_column(); kpi.add_column(style="bold cyan"); kpi.add_column()
    total_port = st["poly_total"] + st["k_total"]
    total_cash = st["poly_cash"] + st["k_cash"]
    pos_count = len(st["positions"])
    lt = st["last_trade"]
    last_trade_str = (f"{lt['side']} @ {lt['price']:.3f} ${lt['size_usd']:.2f} ({_ago(lt['timestamp'])}) {lt['status']}" if lt else "—")
    last_cp = st["last_cp"]
    sched_str = f"{last_cp['stage']} ({_ago(last_cp['timestamp'])})" if last_cp else "never"
    ai_str = f"Claude/{CLAUDE_AUTH_MODE}"
    ml_str = "[green]loaded[/]" if st["ml_loaded"] else "[yellow]stub[/]"
    rl_str = "[green]active[/]" if st["rl_ok"] else "[red]missing[/]"
    err_clr = "[red]" if st["err_1h"] > 10 else "[yellow]" if st["err_1h"] > 0 else "[green]"
    kpi.add_row("Portfolio", f"${total_port:,.2f}",   "Cash",        f"${total_cash:,.2f}")
    kpi.add_row("Positions", f"{pos_count}",          "Kalshi Mkts", f"{st['mk_kalshi'][0]} (last {_ago(st['mk_kalshi'][1])})")
    kpi.add_row("Poly Mkts", f"{st['mk_poly'][0]} (last {_ago(st['mk_poly'][1])})", "Signals 10m", f"{st['sig_10m']}")
    kpi.add_row("Arbitrage", f"{st['arb']} (24h)",    "Last Trade",  last_trade_str)
    kpi.add_row("Scheduler", sched_str,               "AI Model",    ai_str)
    kpi.add_row("ML Model",  ml_str,                  "RL Policy",   rl_str)
    kpi.add_row("Errors 1h", f"{err_clr}{st['err_1h']}[/]",         "Orders 24h",  f"live={st['orders_live']} dry={st['orders_dry']}")
    kpi_panel = Panel(kpi, title="KPIs", border_style="cyan")

    # ─── Balances ───
    bal = Table(expand=True, show_header=True, header_style="bold")
    bal.add_column("Exchange"); bal.add_column("Cash", justify="right"); bal.add_column("Positions", justify="right")
    bal.add_column("Total", justify="right"); bal.add_column("Status")
    bal.add_row("Polymarket", f"${st['poly_cash']:,.2f}", f"${st['poly_pos']:,.2f}", f"${st['poly_total']:,.2f}",
                f"[red]{st['poly_err']}[/]" if st["poly_err"] else "[green]ok[/]")
    def _fmt(v, stale):
        if v is None: return "[dim]n/a[/]"
        prefix = "[yellow]~[/]" if stale else ""
        return f"{prefix}${v:,.2f}"
    k_stale = bool(st["k_err"])
    bal.add_row("Kalshi", _fmt(st['k_cash'], k_stale), _fmt(st['k_pos'], k_stale), _fmt(st['k_total'], k_stale),
                f"[yellow]API DOWN (showing last)[/]" if k_stale else "[green]ok[/]")
    bal_panel = Panel(bal, title="Balances", border_style="green")

    # ─── Positions ───
    if st["positions"]:
        pos = Table(expand=True, show_header=True, header_style="bold")
        pos.add_column("Exchange"); pos.add_column("Side"); pos.add_column("Contracts", justify="right")
        pos.add_column("Exposure", justify="right"); pos.add_column("Market")
        for p in st["positions"]:
            pos.add_row(p["exchange"], p["side"], f"{p['size_contracts']:.1f}", f"${p['exposure_usd']:,.2f}",
                        (p["market_id"] or "")[:40])
        pos_panel = Panel(pos, title=f"Active Positions ({st.get('positions_total', len(st['positions']))})", border_style="blue")
    else:
        pos_panel = Panel("[dim](no positions)[/]", title="Active Positions (0)", border_style="blue")

    # ─── Top Signals ───
    if st["top_sig"]:
        sig = Table(expand=True, show_header=True, header_style="bold")
        sig.add_column("Score", justify="right"); sig.add_column("Conf", justify="right")
        sig.add_column("Strategy"); sig.add_column("Dir"); sig.add_column("Px", justify="right")
        sig.add_column("Src"); sig.add_column("Market")
        for r in st["top_sig"]:
            mark = "[bold red]🚀[/]" if r["combined_score"] >= MIN_SIGNAL_SCORE and r["confidence"] >= MIN_CONFIDENCE_EXEC else ""
            sig.add_row(f"{mark}{r['combined_score']:.1f}", f"{r['confidence']:.2f}",
                        (r["strategy_name"] or "")[:18], (r["direction"] or "")[:10],
                        f"{r['yes_price'] or 0:.3f}", r["source"] or "?", (r["title"] or "")[:45])
        sig_panel = Panel(sig, title=f"Top Signals (last 10m, total={st['sig_10m']}/{st['sig_24h']} 24h)", border_style="magenta")
    else:
        sig_panel = Panel("[dim](no signals in last 10m — scheduler may not be running)[/]",
                          title="Top Signals", border_style="magenta")

    # ─── Arbitrage ───
    if st["arb_sample"]:
        arb = Table(expand=True, show_header=True, header_style="bold")
        arb.add_column("Score", justify="right"); arb.add_column("Market"); arb.add_column("Src")
        for r in st["arb_sample"]:
            arb.add_row(f"{r['score']:.1f}", (r["title"] or r["market_id"] or "")[:60], "cross")
        arb_panel = Panel(arb, title=f"Arbitrage Opportunities ({st['arb']} in 24h)", border_style="yellow")
    else:
        arb_panel = Panel(
            f"[dim](no cross_market signals in 24h — Poly={st['mk_poly'][0]} Kalshi={st['mk_kalshi'][0]} "
            "markets in DB, but no overlapping questions between the two exchanges right now)[/]",
            title="Arbitrage Opportunities (0)", border_style="yellow")

    # ─── Strategy activity ───
    if st["strat_24h"]:
        strat = Table(expand=True, show_header=True, header_style="bold")
        strat.add_column("Strategy"); strat.add_column("Count 24h", justify="right"); strat.add_column("Avg Score", justify="right")
        for r in st["strat_24h"][:8]:
            strat.add_row(r["strategy_name"], str(r["c"]), f"{r['sc']:.1f}")
        strat_panel = Panel(strat, title="Strategy Activity (24h)", border_style="white")
    else:
        strat_panel = Panel("[dim](no strategy signals)[/]", title="Strategy Activity", border_style="white")

    body = Group(kpi_panel, bal_panel, pos_panel, sig_panel, arb_panel, strat_panel)
    return Panel(Group(header, body), border_style="bright_blue")


def main():
    console = Console()
    try:
        with Live(_render(_fetch_state()), console=console, refresh_per_second=1, screen=False) as live:
            import time as _t
            while True:
                _t.sleep(2)
                try:
                    live.update(_render(_fetch_state()))
                except Exception as e:
                    live.update(Panel(f"[red]dashboard render error: {e}[/]", title="UPAS DASHBOARD"))
    except KeyboardInterrupt:
        console.print("\n[dashboard] exited.")


if __name__ == "__main__":
    main()
