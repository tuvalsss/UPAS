"""
tools/cli.py
Interactive CLI command interface for UPAS.
Run: python -m tools.cli

Commands:
  status               system health summary
  portfolio            balances (poly + kalshi)
  positions            active positions
  signals [n]          top N signals from last 10m (default 10)
  markets [src]        market count, optional source filter
  arb                  recent cross-market arbitrage signals
  orders [n]           last N orders (default 10)
  run                  run ONE scheduler cycle now
  force-scan           refresh markets from both exchanges
  run-strategy <name>  run a single strategy by name
  pause                write PAUSE flag (scheduler skips execute stage)
  resume               clear PAUSE flag
  close <market_id>    mark position for close (writes close request)
  errors [n]           last N errors from log
  ask <question>       ask Claude a free-form question about the system
  scorecard            per-strategy realized win-rate + adaptive weights
  track                force one outcome-tracker pass (normally every 30 min)
  train                train ML re-ranker on accumulated outcomes
  propose              ask Claude to propose a new strategy (>=500 outcomes needed)
  help                 this list
  exit / quit          leave REPL
"""
from __future__ import annotations

import sys
import json
from datetime import datetime, timezone
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from tools.database_tool import _conn, get_recent_orders
from tools.account_tool import get_polymarket_account, get_kalshi_balance
from config.variables import DRY_RUN, AUTO_EXECUTE, CLAUDE_AUTH_MODE

_ROOT = Path(__file__).parent.parent
_PAUSE_FLAG = _ROOT / ".pause"
_CLOSE_QUEUE = _ROOT / ".close_queue.jsonl"
_LOG_FILE = _ROOT / "logs" / "upas.jsonl"

console = Console()


def _ago(ts):
    if not ts: return "—"
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


def cmd_status(_):
    mode = "LIVE" if (AUTO_EXECUTE and not DRY_RUN) else "DRY"
    paused = _PAUSE_FLAG.exists()
    with _conn() as con:
        m_poly = con.execute("SELECT COUNT(*), MAX(fetched_at) FROM markets WHERE source='polymarket'").fetchone()
        m_kal = con.execute("SELECT COUNT(*), MAX(fetched_at) FROM markets WHERE source='kalshi'").fetchone()
        sig10 = con.execute("SELECT COUNT(*) FROM signals WHERE timestamp>=datetime('now','-10 minutes')").fetchone()[0]
        arb = con.execute("SELECT COUNT(*) FROM signals WHERE strategy_name='cross_market' AND timestamp>=datetime('now','-1 day')").fetchone()[0]
        last_cp = con.execute("SELECT stage,timestamp FROM checkpoints ORDER BY timestamp DESC LIMIT 1").fetchone()
        live_24h = con.execute("SELECT COUNT(*) FROM orders WHERE dry_run=0 AND timestamp>=datetime('now','-1 day')").fetchone()[0]
    t = Table(show_header=False, box=None)
    t.add_column(style="cyan bold"); t.add_column()
    t.add_row("mode", f"[{'red' if mode=='LIVE' else 'green'} bold]{mode}[/]")
    t.add_row("paused", "[yellow]YES[/]" if paused else "[green]no[/]")
    t.add_row("auth", f"Claude/{CLAUDE_AUTH_MODE}")
    t.add_row("polymarket markets", f"{m_poly[0]} (last {_ago(m_poly[1])})")
    t.add_row("kalshi markets", f"{m_kal[0]} (last {_ago(m_kal[1])})")
    t.add_row("signals 10m", str(sig10))
    t.add_row("arbitrage 24h", str(arb))
    t.add_row("live orders 24h", str(live_24h))
    t.add_row("last checkpoint", f"{last_cp['stage']} ({_ago(last_cp['timestamp'])})" if last_cp else "never")
    console.print(Panel(t, title="UPAS STATUS", border_style="cyan"))


def cmd_portfolio(_):
    t = Table(show_header=True, header_style="bold")
    t.add_column("Exchange"); t.add_column("Cash", justify="right"); t.add_column("Positions", justify="right")
    t.add_column("Total", justify="right")
    try:
        p = get_polymarket_account()
        t.add_row("Polymarket", f"${p.get('cash_balance_usd',0):,.2f}",
                  f"${p.get('positions_value_usd',0):,.2f}", f"${p.get('total_value_usd',0):,.2f}")
    except Exception as e:
        t.add_row("Polymarket", f"[red]ERR: {e}[/]", "-", "-")
    try:
        k = get_kalshi_balance()
        t.add_row("Kalshi", f"${k.get('cash_balance_usd',0):,.2f}",
                  f"${k.get('portfolio_value_usd',0):,.2f}", f"${k.get('total_value_usd',0):,.2f}")
    except Exception as e:
        t.add_row("Kalshi", f"[red]ERR: {e}[/]", "-", "-")
    console.print(Panel(t, title="Portfolio", border_style="green"))


def cmd_positions(_):
    with _conn() as con:
        rows = con.execute(
            "SELECT exchange,market_id,side,size_contracts,exposure_usd,last_updated FROM positions WHERE size_contracts>0 ORDER BY exposure_usd DESC"
        ).fetchall()
    if not rows:
        console.print("[dim](no active positions)[/]"); return
    t = Table(show_header=True, header_style="bold")
    t.add_column("Exch"); t.add_column("Market"); t.add_column("Side")
    t.add_column("Size", justify="right"); t.add_column("Exposure", justify="right"); t.add_column("Updated")
    for r in rows:
        t.add_row(r["exchange"], (r["market_id"] or "")[:40], r["side"],
                  f"{r['size_contracts']:.2f}", f"${r['exposure_usd']:,.2f}", _ago(r["last_updated"]))
    console.print(t)


def cmd_signals(args):
    n = int(args[0]) if args and args[0].isdigit() else 10
    with _conn() as con:
        rows = con.execute(
            """SELECT s.strategy_name, s.direction, sc.combined_score, sc.confidence,
                      s.market_id, m.title, m.yes_price, m.source
               FROM signals s JOIN scores sc ON s.signal_id=sc.signal_id
               LEFT JOIN markets m ON s.market_id=m.market_id
               WHERE s.timestamp>=datetime('now','-10 minutes')
               ORDER BY sc.combined_score DESC LIMIT ?""", (n,)
        ).fetchall()
    if not rows:
        console.print("[dim](no signals in last 10m)[/]"); return
    t = Table(show_header=True, header_style="bold")
    t.add_column("Score", justify="right"); t.add_column("Conf", justify="right")
    t.add_column("Strategy"); t.add_column("Dir"); t.add_column("Px", justify="right")
    t.add_column("Src"); t.add_column("Market")
    for r in rows:
        t.add_row(f"{r['combined_score']:.1f}", f"{r['confidence']:.2f}",
                  (r["strategy_name"] or "")[:18], (r["direction"] or "")[:8],
                  f"{r['yes_price'] or 0:.3f}", r["source"] or "?", (r["title"] or r["market_id"] or "")[:50])
    console.print(t)


def cmd_markets(args):
    src = args[0] if args else None
    with _conn() as con:
        if src:
            rows = con.execute("SELECT source,COUNT(*) c,MAX(fetched_at) last FROM markets WHERE source=? GROUP BY source", (src,)).fetchall()
        else:
            rows = con.execute("SELECT source,COUNT(*) c,MAX(fetched_at) last FROM markets GROUP BY source").fetchall()
    t = Table(show_header=True, header_style="bold")
    t.add_column("Source"); t.add_column("Count", justify="right"); t.add_column("Last Fetch")
    for r in rows:
        t.add_row(r["source"], str(r["c"]), _ago(r["last"]))
    console.print(t)


def cmd_arb(_):
    with _conn() as con:
        rows = con.execute(
            """SELECT s.market_id, s.score, s.reasoning, m.title, m.source, s.timestamp
               FROM signals s LEFT JOIN markets m ON s.market_id=m.market_id
               WHERE s.strategy_name='cross_market'
               ORDER BY s.timestamp DESC LIMIT 10"""
        ).fetchall()
    if not rows:
        console.print("[dim](no cross-market arbitrage in DB — requires both polymarket+kalshi markets)[/]"); return
    for r in rows:
        console.print(f"[yellow]score={r['score']:.1f}[/] [{_ago(r['timestamp'])}] {(r['title'] or r['market_id'])[:60]}")
        if r["reasoning"]:
            console.print(f"  [dim]{r['reasoning'][:150]}[/]")


def cmd_orders(args):
    n = int(args[0]) if args and args[0].isdigit() else 10
    orders = get_recent_orders(hours=48)[:n]
    if not orders: console.print("[dim](no orders)[/]"); return
    t = Table(show_header=True, header_style="bold")
    t.add_column("When"); t.add_column("Exch"); t.add_column("Mode"); t.add_column("Side")
    t.add_column("Px", justify="right"); t.add_column("$", justify="right"); t.add_column("Status"); t.add_column("Market")
    for o in orders:
        mode = "[red]LIVE[/]" if not o.get("dry_run") else "dry"
        t.add_row(_ago(o["timestamp"]), o["exchange"], mode, o["side"][:4],
                  f"{o.get('price',0):.3f}", f"${o.get('size_usd',0):.2f}",
                  o["status"][:9], (o["market_id"] or "")[:40])
    console.print(t)


def cmd_run(_):
    console.print("[cyan]running single scheduler cycle...[/]")
    from core.engine import run_pipeline
    try:
        result = run_pipeline()
        console.print(f"[green]cycle complete[/] signals={result.get('signals_count', '?')} "
                      f"executed={result.get('executed_count', '?')}")
    except Exception as e:
        console.print(f"[red]cycle failed: {e}[/]")


def cmd_force_scan(_):
    console.print("[cyan]refreshing markets from both exchanges...[/]")
    from tools.polymarket_tool import run as run_poly
    from tools.kalshi_tool import run as run_kal
    from tools.database_tool import upsert_market
    for label, fn in (("polymarket", run_poly), ("kalshi", run_kal)):
        try:
            r = fn(limit=500)
            saved = 0
            for m in r.get("markets", []):
                try:
                    upsert_market(m); saved += 1
                except Exception:
                    pass
            console.print(f"  {label}: fetched={r.get('count',0)} saved={saved}")
        except Exception as e:
            console.print(f"  [red]{label}: {e}[/]")


def cmd_run_strategy(args):
    if not args:
        console.print("[red]usage: run-strategy <name>[/]"); return
    name = args[0]
    console.print(f"[cyan]running strategy: {name}[/]")
    try:
        import importlib
        mod = importlib.import_module(f"strategies.core.{name}")
        from tools.database_tool import load_recent_markets
        markets = load_recent_markets(hours=1)
        sigs = mod.run(markets) if hasattr(mod, "run") else []
        console.print(f"[green]{name}: {len(sigs)} signals[/]")
        for s in sigs[:5]:
            console.print(f"  score={s.get('score', 0):.1f} {s.get('market_id', '')[:40]} {s.get('direction', '')}")
    except Exception as e:
        console.print(f"[red]error: {e}[/]")


def cmd_pause(_):
    _PAUSE_FLAG.write_text(datetime.now(timezone.utc).isoformat())
    console.print("[yellow]PAUSE flag set — scheduler will skip execute stage[/]")


def cmd_resume(_):
    if _PAUSE_FLAG.exists():
        _PAUSE_FLAG.unlink()
        console.print("[green]PAUSE flag cleared[/]")
    else:
        console.print("[dim](not paused)[/]")


def cmd_close(args):
    if not args:
        console.print("[red]usage: close <market_id>[/]"); return
    mid = args[0]
    with open(_CLOSE_QUEUE, "a", encoding="utf-8") as f:
        f.write(json.dumps({"market_id": mid, "requested_at": datetime.now(timezone.utc).isoformat()}) + "\n")
    console.print(f"[yellow]close requested for {mid} — next scheduler cycle will process[/]")


def cmd_errors(args):
    n = int(args[0]) if args and args[0].isdigit() else 10
    if not _LOG_FILE.exists():
        console.print("[dim](no log file)[/]"); return
    errs = []
    with open(_LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
        try:
            import os as _os
            f.seek(max(0, _os.path.getsize(_LOG_FILE) - 500_000))
            f.readline()
        except Exception:
            pass
        for line in f:
            try:
                e = json.loads(line)
                if e.get("level") in ("ERROR", "CRITICAL"):
                    errs.append(e)
            except Exception:
                continue
    for e in errs[-n:]:
        ts = e.get("timestamp", "")[:19]
        console.print(f"[red]{ts}[/] [{e.get('source', '?')}] {e.get('message', '')}  "
                      f"[dim]{e.get('error') or ''}[/]")


def cmd_ask(args):
    if not args:
        console.print("[yellow]usage: ask <question>[/]"); return
    question = " ".join(args).strip()
    try:
        from ai.scorer import _call_claude
    except Exception as e:
        console.print(f"[red]ai.scorer unavailable: {e}[/]"); return
    with _conn() as con:
        poly_n = con.execute("SELECT COUNT(*) FROM markets WHERE source='polymarket'").fetchone()[0]
        kalshi_n = con.execute("SELECT COUNT(*) FROM markets WHERE source='kalshi'").fetchone()[0]
        sig_24h = con.execute("SELECT COUNT(*) FROM signals WHERE timestamp>=datetime('now','-1 day')").fetchone()[0]
        orders_24h = con.execute("SELECT COUNT(*) FROM orders WHERE timestamp>=datetime('now','-1 day')").fetchone()[0]
    ctx = (
        f"System context: UPAS prediction-market alpha engine. DRY_RUN={DRY_RUN} AUTO_EXECUTE={AUTO_EXECUTE}. "
        f"Markets in DB: poly={poly_n} kalshi={kalshi_n}. Last 24h: signals={sig_24h} orders={orders_24h}. "
        f"User question:\n{question}"
    )
    try:
        answer = _call_claude(ctx, tier="B")
    except Exception as e:
        console.print(f"[red]AI call failed: {e}[/]"); return
    console.print(Panel(answer or "[dim](empty)[/]", title="Claude", border_style="magenta"))


def cmd_scorecard(_):
    """Per-strategy realized win-rate + PnL + current adaptive weight."""
    from core.strategy_scorecard import scorecard, grand_total
    from core.strategy_weights import list_all
    gt = grand_total()
    console.print(Panel(
        f"Trades: [bold]{gt['trades']}[/]    "
        f"W/L: [green]{gt['wins']}[/]/[red]{gt['losses']}[/]    "
        f"Win rate: [bold]{gt['win_rate']*100:.1f}%[/]    "
        f"Total PnL: {'[green]' if gt['total_pnl_usd']>=0 else '[red]'}"
        f"${gt['total_pnl_usd']:+.2f}[/]",
        title="Realized Outcomes", border_style="cyan",
    ))
    cards = scorecard()
    weights = {w["strategy"]: w for w in list_all()}
    t = Table(title="Per-Strategy Scorecard", show_lines=False)
    for col in ["Strategy", "n", "W/L", "WinRate", "AvgPnL", "TotalPnL", "Weight", "Status"]:
        t.add_column(col)
    for c in cards:
        w = weights.get(c["strategy"], {})
        weight = w.get("weight", 1.0)
        enabled = w.get("enabled", True)
        status = "[red]DISABLED[/]" if not enabled else (f"[green]BOOST×{weight}[/]" if weight > 1.0 else "normal")
        pnl_color = "green" if c["total_pnl_usd"] >= 0 else "red"
        t.add_row(
            c["strategy"], str(c["n"]), f"{c['wins']}/{c['losses']}",
            f"{c['win_rate']*100:.1f}%", f"${c['avg_pnl_usd']:+.2f}",
            f"[{pnl_color}]${c['total_pnl_usd']:+.2f}[/]", f"{weight:.2f}", status,
        )
    console.print(t)


def cmd_track_once(_):
    """Force a single outcome_tracker pass (usually daemon runs this every 30 min)."""
    from core.outcome_tracker import run_once
    r = run_once()
    console.print(Panel(json.dumps(r, indent=2), title="Outcome Tracker", border_style="cyan"))


def cmd_help(_):
    console.print(Panel(__doc__ or "(no help)", title="UPAS CLI", border_style="bright_blue"))


COMMANDS = {
    "status": cmd_status, "portfolio": cmd_portfolio, "positions": cmd_positions,
    "signals": cmd_signals, "markets": cmd_markets, "arb": cmd_arb, "orders": cmd_orders,
    "run": cmd_run, "force-scan": cmd_force_scan, "run-strategy": cmd_run_strategy,
    "pause": cmd_pause, "resume": cmd_resume, "close": cmd_close, "errors": cmd_errors,
    "ask": cmd_ask,
    "scorecard": cmd_scorecard, "track": cmd_track_once,
    "train": lambda _: console.print(__import__("ml.reranker", fromlist=["train"]).train()),
    "propose": lambda _: console.print(__import__("ai.strategy_generator", fromlist=["propose_one"]).propose_one()),
    "help": cmd_help, "?": cmd_help,
}


def main():
    console.print(Panel("UPAS Interactive CLI. Type [cyan]help[/] for commands, [cyan]exit[/] to quit.",
                        border_style="bright_blue"))
    while True:
        try:
            line = input("\nupas> ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[cli] exiting."); return
        if not line: continue
        parts = line.split()
        cmd, args = parts[0].lower(), parts[1:]
        if cmd in ("exit", "quit"):
            console.print("[cli] bye."); return
        fn = COMMANDS.get(cmd)
        if not fn:
            console.print(f"[red]unknown command: {cmd}[/]  (type 'help')"); continue
        try:
            fn(args)
        except Exception as e:
            console.print(f"[red]command error: {e}[/]")


if __name__ == "__main__":
    main()
