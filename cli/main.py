"""
cli/main.py
UPAS command-line interface — all commands work on Windows PowerShell.
Every command supports --json and --verbose flags.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Force UTF-8 stdout/stderr on Windows to avoid cp125x codec crashes when
# printing Unicode characters (✓ ✗ etc.) in legacy terminal code pages.
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint

# Ensure project root is on sys.path (for running as python cli/main.py)
_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# legacy_windows=False: skip Win32 Console API and write directly to stdout,
# preventing UnicodeEncodeError in non-UTF-8 terminal code pages (e.g. cp1255).
console = Console(legacy_windows=False)


# ── Shared output helper ─────────────────────────────────────
def _output(data: dict | list, as_json: bool) -> None:
    if as_json:
        click.echo(json.dumps(data, indent=2, default=str))
    else:
        rprint(data)


# ── Root command group ────────────────────────────────────────
@click.group()
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@click.option("--verbose", "-v", is_flag=True, help="Verbose logging")
@click.option("--strict", is_flag=True, help="Force ask-before-assuming on every inference")
@click.option("--reverse", is_flag=True, help="Run uncertainty checks first before each stage")
@click.pass_context
def cli(ctx, as_json, verbose, strict, reverse):
    """UPAS — Universal Prediction Alpha System"""
    ctx.ensure_object(dict)
    ctx.obj["json"] = as_json
    ctx.obj["verbose"] = verbose
    ctx.obj["strict"] = strict
    ctx.obj["reverse"] = reverse

    if strict:
        import os
        os.environ["ASK_BEFORE_ASSUMING"] = "true"


# ── init ─────────────────────────────────────────────────────
@cli.command()
@click.pass_context
def init(ctx):
    """Initialize database, config, checkpoints, and tool registry."""
    as_json = ctx.obj["json"]
    if not as_json:
        console.print("[bold cyan]Initializing UPAS...[/bold cyan]")

    try:
        from database.schema import init_database, get_schema_info
        from config.variables import DATABASE_PATH, CHECKPOINT_PATH
        from tools.tool_registry import snapshot

        # Create data directories
        DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CHECKPOINT_PATH.mkdir(parents=True, exist_ok=True)
        Path(_ROOT / "logs").mkdir(parents=True, exist_ok=True)

        # Initialize database
        init_database()
        schema = get_schema_info()

        # Snapshot tool registry
        reg = snapshot()

        result = {
            "status": "ok",
            "database": str(DATABASE_PATH),
            "tables": schema.get("tables", []),
            "checkpoint_dir": str(CHECKPOINT_PATH),
            "tools_registered": reg["tool_count"],
        }

        if as_json:
            _output(result, True)
        else:
            console.print(f"[green]✓[/green] Database: {DATABASE_PATH}")
            console.print(f"[green]✓[/green] Tables: {len(schema.get('tables', []))} created")
            console.print(f"[green]✓[/green] Checkpoints dir: {CHECKPOINT_PATH}")
            console.print(f"[green]✓[/green] Tools registered: {reg['tool_count']}")
            console.print("\n[bold green]UPAS initialized successfully.[/bold green]")

    except Exception as e:
        error = {"status": "error", "error": str(e)}
        if as_json:
            _output(error, True)
        else:
            console.print(f"[red]✗ Init failed: {e}[/red]")
        sys.exit(1)


# ── scan ─────────────────────────────────────────────────────
@cli.command()
@click.pass_context
def scan(ctx):
    """Run one full pipeline pass: scan → strategies → score → alert → checkpoint."""
    as_json = ctx.obj["json"]
    verbose = ctx.obj["verbose"]
    strict = ctx.obj["strict"]

    if not as_json:
        console.print("[bold cyan]Running pipeline scan...[/bold cyan]")

    try:
        from core.engine import run_pipeline
        result = run_pipeline(verbose=verbose, strict=strict, non_interactive=as_json)

        if as_json:
            # Strip bulky ranked_signals for clean JSON output summary
            out = {k: v for k, v in result.items() if k != "ranked_signals"}
            out["top_signals"] = result.get("ranked_signals", [])[:10]
            _output(out, True)
        else:
            ranked = result.get("ranked_signals", [])
            console.print(f"\n[green]✓[/green] Markets scanned: {result['markets_scanned']}")
            console.print(f"[green]✓[/green] Signals generated: {result['signals_generated']}")
            console.print(f"[green]✓[/green] Alerts sent: {result['alerts_sent']}")

            if ranked:
                table = Table(title="Top Signals", show_header=True)
                table.add_column("Score", style="bold yellow", width=7)
                table.add_column("Strategy", width=22)
                table.add_column("Direction", width=10)
                table.add_column("Action", width=12)
                table.add_column("Market", width=50)
                for s in ranked[:10]:
                    table.add_row(
                        f"{s.get('combined_score', 0):.1f}",
                        s.get("strategy_name", ""),
                        s.get("direction", ""),
                        s.get("suggested_action", ""),
                        s.get("title", s.get("market_id", ""))[:48],
                    )
                console.print(table)

    except Exception as e:
        if as_json:
            _output({"status": "error", "error": str(e)}, True)
        else:
            console.print(f"[red]✗ Scan failed: {e}[/red]")
            if verbose:
                import traceback; traceback.print_exc()
        sys.exit(1)


# ── live ─────────────────────────────────────────────────────
@cli.command()
@click.pass_context
def live(ctx):
    """Start continuous scan mode. Press Ctrl+C to stop safely."""
    verbose = ctx.obj["verbose"]
    strict = ctx.obj["strict"]

    console.print("[bold cyan]Starting live mode...[/bold cyan]")
    console.print("Press [bold]Ctrl+C[/bold] to stop (state will be checkpointed).\n")

    from core.scheduler import run_continuous
    run_continuous(verbose=verbose, strict=strict, non_interactive=False)


# ── status ────────────────────────────────────────────────────
@cli.command()
@click.pass_context
def status(ctx):
    """Show last checkpoint and system health."""
    as_json = ctx.obj["json"]

    from tools.checkpoint_tool import status as cp_status
    from tools.tool_registry import list_tools
    from config.variables import DATABASE_PATH

    cp = cp_status()
    db_exists = DATABASE_PATH.exists()

    result = {
        "checkpoint": cp,
        "database": {"exists": db_exists, "path": str(DATABASE_PATH)},
        "tools": len(list_tools()),
    }

    if as_json:
        _output(result, True)
    else:
        console.print(Panel(
            f"Checkpoint: [{'green' if cp['has_checkpoint'] else 'red'}]{cp['has_checkpoint']}[/]\n"
            f"Stage: {cp.get('stage', 'N/A')}\n"
            f"Time: {cp.get('timestamp', 'N/A')}\n"
            f"Resumable: {cp.get('resumable', False)}\n"
            f"Database: {'[green]exists[/green]' if db_exists else '[red]missing[/red]'}\n"
            f"Tools: {len(list_tools())} registered",
            title="UPAS Status",
        ))


# ── replay ────────────────────────────────────────────────────
@cli.command()
@click.pass_context
def replay(ctx):
    """Resume pipeline from last checkpoint."""
    as_json = ctx.obj["json"]

    from tools.checkpoint_tool import load
    cp = load()

    if not cp:
        msg = "No checkpoint found. Run 'scan' first."
        if as_json:
            _output({"status": "error", "error": msg}, True)
        else:
            console.print(f"[red]{msg}[/red]")
        sys.exit(1)

    if not as_json:
        console.print(f"[cyan]Resuming from stage: {cp.get('stage')} ({cp.get('timestamp')})[/cyan]")

    from core.engine import run_pipeline
    result = run_pipeline(
        run_id=cp.get("run_id"),
        verbose=ctx.obj["verbose"],
        non_interactive=as_json,
    )

    if as_json:
        _output(result, True)
    else:
        console.print(f"[green]✓[/green] Replay complete. Signals: {result.get('signals_generated')}")


# ── analyze ───────────────────────────────────────────────────
@cli.command()
@click.argument("id")
@click.pass_context
def analyze(ctx, id):
    """Deep-dive analysis of a market or signal by ID."""
    as_json = ctx.obj["json"]

    from tools.database_tool import get_signal_by_id, get_market
    sig = get_signal_by_id(id)

    if not sig:
        if as_json:
            _output({"status": "not_found", "id": id}, True)
        else:
            console.print(f"[red]Signal {id} not found.[/red]")
        return

    from ai.reasoning import explain
    reasoning = explain(sig)

    result = {**sig, "reasoning_detail": reasoning}
    if as_json:
        _output(result, True)
    else:
        console.print(Panel(
            f"Signal ID: {sig.get('signal_id')}\n"
            f"Strategy: {sig.get('strategy_name')}\n"
            f"Direction: {sig.get('direction')}\n"
            f"Score: {sig.get('score', 0):.1f}\n"
            f"Action: {sig.get('suggested_action')}\n"
            f"Reasoning: {sig.get('reasoning', '')[:200]}\n\n"
            f"[bold]Verdict:[/bold] {reasoning.get('verdict')}\n"
            f"{reasoning.get('confidence_narrative', '')}",
            title=f"Signal Analysis: {id[:16]}...",
        ))


# ── explain ───────────────────────────────────────────────────
@cli.command()
@click.argument("signal_id")
@click.pass_context
def explain(ctx, signal_id):
    """Show full AI reasoning for a signal."""
    ctx.invoke(analyze, id=signal_id)


# ── train ─────────────────────────────────────────────────────
@cli.command()
@click.pass_context
def train(ctx):
    """Trigger XGBoost ML training on stored outcomes."""
    as_json = ctx.obj["json"]

    if not as_json:
        console.print("[bold cyan]Starting ML training...[/bold cyan]")

    from ml.trainer import train as ml_train
    result = ml_train()

    if as_json:
        _output(result, True)
    else:
        if result.get("success"):
            metrics = result.get("metrics", {})
            console.print(f"[green]✓[/green] Training complete!")
            console.print(f"  Accuracy: {metrics.get('accuracy', 0):.2%}")
            console.print(f"  AUC: {metrics.get('auc', 0):.4f}")
            console.print(f"  Model: {result.get('model_path')}")
        else:
            console.print(f"[red]✗ Training failed: {result.get('reason')}[/red]")


# ── export ────────────────────────────────────────────────────
@cli.command()
@click.option("--format", "fmt", default="json", type=click.Choice(["json", "csv"]))
@click.option("--limit", default=1000, type=int)
@click.option("--output", "-o", default=None, help="Output file path")
@click.pass_context
def export(ctx, fmt, limit, output):
    """Export signals to JSON or CSV."""
    from tools.database_tool import export_signals
    signals = export_signals(limit=limit)

    if fmt == "json":
        content = json.dumps(signals, indent=2, default=str)
        ext = "json"
    else:
        import csv, io
        buf = io.StringIO()
        if signals:
            writer = csv.DictWriter(buf, fieldnames=signals[0].keys())
            writer.writeheader()
            writer.writerows(signals)
        content = buf.getvalue()
        ext = "csv"

    if output:
        Path(output).write_text(content, encoding="utf-8")
        console.print(f"[green]✓[/green] Exported {len(signals)} signals to {output}")
    else:
        click.echo(content)


# ── backtest ──────────────────────────────────────────────────
@cli.command()
@click.pass_context
def backtest(ctx):
    """Run strategies against historical data."""
    as_json = ctx.obj["json"]
    from tools.database_tool import get_recent_markets
    markets = get_recent_markets(limit=500)

    if not markets:
        msg = "No historical markets found. Run scan first."
        _output({"status": "error", "error": msg}, True) if as_json else console.print(f"[red]{msg}[/red]")
        return

    from tools.strategy_tool import run_strategies
    forward = run_strategies(markets, "core")
    reverse = run_strategies(markets, "reverse")

    result = {
        "historical_markets": len(markets),
        "forward_signals": len(forward),
        "reverse_signals": len(reverse),
        "strategies_run": ["core", "reverse"],
    }
    _output(result, True) if as_json else console.print(f"[green]Backtest:[/green] {result}")


# ── doctor ────────────────────────────────────────────────────
@cli.command()
@click.pass_context
def doctor(ctx):
    """Verify environment, dependencies, and API connectivity."""
    as_json = ctx.obj["json"]
    checks = {}

    # Python version
    v = sys.version_info
    checks["python_version"] = {
        "ok": v >= (3, 10),
        "value": f"{v.major}.{v.minor}.{v.micro}",
    }

    # Required packages
    for pkg in ["click", "rich", "yaml", "requests", "dotenv", "xgboost", "numpy", "pandas"]:
        try:
            __import__(pkg if pkg != "dotenv" else "dotenv")
            checks[f"pkg_{pkg}"] = {"ok": True}
        except ImportError:
            checks[f"pkg_{pkg}"] = {"ok": False, "error": "not installed"}

    # Database
    from config.variables import DATABASE_PATH
    checks["database"] = {
        "ok": DATABASE_PATH.exists(),
        "path": str(DATABASE_PATH),
    }
    if not DATABASE_PATH.exists():
        checks["database"]["hint"] = "Run: python cli/main.py init"

    # .env file
    checks["env_file"] = {"ok": (_ROOT / ".env").exists()}

    # Kalshi key
    from config.variables import KALSHI_PRIVATE_KEY_PATH
    checks["kalshi_key"] = {"ok": Path(KALSHI_PRIVATE_KEY_PATH).exists()}

    # Polymarket credentials
    from config.variables import POLY_API_KEY
    checks["poly_credentials"] = {"ok": bool(POLY_API_KEY)}

    # Polymarket API reachability (Gamma — no auth required)
    try:
        import requests as _req
        from config.variables import POLY_GAMMA_BASE
        r = _req.get(f"{POLY_GAMMA_BASE}/markets", params={"limit": 1}, timeout=8)
        checks["polymarket_api"] = {"ok": r.status_code < 500, "status": r.status_code}
    except Exception as e:
        checks["polymarket_api"] = {"ok": False, "error": str(e)[:80]}

    # Kalshi API reachability (unauthenticated probe)
    try:
        from config.variables import KALSHI_BASE
        r = _req.get(
            f"{KALSHI_BASE.removesuffix('/trade-api/v2')}/trade-api/v2/exchange/status",
            timeout=8,
        )
        checks["kalshi_api"] = {"ok": r.status_code < 500, "status": r.status_code}
    except Exception as e:
        checks["kalshi_api"] = {"ok": False, "error": str(e)[:80]}

    all_ok = all(v.get("ok", False) for v in checks.values())

    if as_json:
        _output({"all_ok": all_ok, "checks": checks}, True)
    else:
        console.print("\n[bold]UPAS Doctor Report[/bold]")
        for name, check in checks.items():
            icon = "[green]✓[/green]" if check.get("ok") else "[red]✗[/red]"
            extra = check.get("error") or check.get("hint") or check.get("value") or ""
            console.print(f"  {icon} {name:<30} {extra}")
        if all_ok:
            console.print("\n[bold green]All checks passed.[/bold green]")
        else:
            console.print("\n[bold red]Some checks failed. See above.[/bold red]")


# ── outcome ───────────────────────────────────────────────────
@cli.command()
@click.option("--signal-id", required=True, help="UUID of the signal to resolve")
@click.option("--outcome", "outcome_val", required=True, type=click.Choice(["1", "0"]),
              help="1=correct prediction, 0=wrong prediction")
@click.option("--market-id", default=None, help="Market ID (resolved automatically if omitted)")
@click.pass_context
def outcome(ctx, signal_id, outcome_val, market_id):
    """Record a realized outcome for a signal (needed for ML training)."""
    import uuid as _uuid
    from tools.database_tool import get_signal_by_id, insert_result

    sig = get_signal_by_id(signal_id)
    if not sig:
        console.print(f"[red]Signal {signal_id} not found.[/red]")
        sys.exit(1)

    resolved_market_id = market_id or sig.get("market_id", "")
    result = {
        "result_id": str(_uuid.uuid4()),
        "signal_id": signal_id,
        "market_id": resolved_market_id,
        "realized_outcome": int(outcome_val),
    }
    insert_result(result)

    if ctx.obj["json"]:
        _output({"status": "recorded", **result}, True)
    else:
        label = "[green]CORRECT[/green]" if outcome_val == "1" else "[red]WRONG[/red]"
        console.print(f"[green]✓[/green] Outcome recorded: signal {signal_id[:16]}… → {label}")


# ── ask ───────────────────────────────────────────────────────
@cli.command()
@click.argument("question")
@click.pass_context
def ask(ctx, question):
    """Submit a clarification directly to the pipeline."""
    from core.question_router import ask as route_ask
    result = route_ask(
        stage="user_direct",
        issue=question,
        non_interactive=False,
    )
    if ctx.obj["json"]:
        _output(result, True)
    else:
        console.print(f"[cyan]Answer recorded:[/cyan] {result.get('answer')}")


# ── tools ─────────────────────────────────────────────────────
@cli.command("tools")
@click.pass_context
def list_tools_cmd(ctx):
    """List all registered tools and their status."""
    from tools.tool_registry import list_tools
    tools = list_tools()

    if ctx.obj["json"]:
        _output(tools, True)
    else:
        table = Table(title="Registered Tools")
        table.add_column("Name", style="bold cyan")
        table.add_column("Status")
        table.add_column("Description")
        for t in tools:
            table.add_row(t["name"], t.get("status", "active"), t.get("description", "")[:60])
        console.print(table)


# ── balance ───────────────────────────────────────────────────
@cli.command()
@click.option("--exchange", default="all", type=click.Choice(["all", "kalshi", "polymarket"]))
@click.pass_context
def balance(ctx, exchange):
    """Show live account balances from Polymarket and/or Kalshi."""
    as_json = ctx.obj["json"]

    if not as_json:
        console.print("[bold cyan]Fetching live balances...[/bold cyan]")

    try:
        from tools.account_tool import get_kalshi_balance, get_polymarket_account, get_all_balances
        from tools.database_tool import snapshot_balance

        if exchange == "all":
            result = get_all_balances()
        elif exchange == "kalshi":
            result = {"kalshi": get_kalshi_balance(), "polymarket": None}
        else:
            result = {"kalshi": None, "polymarket": get_polymarket_account()}

        # Persist snapshots
        if result.get("kalshi") and not result["kalshi"].get("error"):
            k = result["kalshi"]
            snapshot_balance("kalshi", k.get("cash_balance_usd", 0), k.get("portfolio_value_usd", 0))
        if result.get("polymarket") and not result["polymarket"].get("error"):
            p = result["polymarket"]
            snapshot_balance("polymarket", p.get("usdc_balance", 0), p.get("portfolio_value_usd", 0))

        if as_json:
            _output(result, True)
        else:
            if result.get("kalshi") and not result["kalshi"].get("error"):
                k = result["kalshi"]
                console.print(f"\n[bold yellow]Kalshi[/bold yellow]")
                console.print(f"  Cash:      [green]${k.get('cash_balance_usd', 0):.2f}[/green]")
                console.print(f"  Portfolio: [green]${k.get('portfolio_value_usd', 0):.2f}[/green]")
                console.print(f"  Total:     [bold green]${k.get('total_value_usd', 0):.2f}[/bold green]")
            if result.get("polymarket") and not result["polymarket"].get("error"):
                p = result["polymarket"]
                portfolio_val = p.get("portfolio_value_usd", 0)
                total_val = p.get("total_value_usd", p.get("usdc_balance", 0) + portfolio_val)
                console.print(f"\n[bold blue]Polymarket[/bold blue]")
                console.print(f"  Wallet:    {p.get('wallet_address', 'N/A')}")
                console.print(f"  USDC:      [green]${p.get('usdc_balance', 0):.2f}[/green]")
                console.print(f"  Portfolio: [green]${portfolio_val:.2f}[/green]")
                console.print(f"  Total:     [bold green]${total_val:.2f}[/bold green]")
                console.print(f"  Open orders: {p.get('open_orders', 0)}")
                console.print(f"  Trade history: {p.get('recent_trades', 0)} recent fills")
    except Exception as e:
        err = {"status": "error", "error": str(e)}
        if as_json:
            _output(err, True)
        else:
            console.print(f"[red]✗ Balance fetch failed: {e}[/red]")
        sys.exit(1)


# ── positions ─────────────────────────────────────────────────
@cli.command()
@click.option("--exchange", default="all", type=click.Choice(["all", "kalshi", "polymarket"]))
@click.pass_context
def positions(ctx, exchange):
    """Show all open positions and P&L."""
    as_json = ctx.obj["json"]

    if not as_json:
        console.print("[bold cyan]Fetching live positions...[/bold cyan]")

    try:
        from tools.account_tool import get_kalshi_positions, get_kalshi_open_orders, get_polymarket_account
        from tools.database_tool import snapshot_positions

        result: dict = {}

        if exchange in ("all", "kalshi"):
            kp = get_kalshi_positions()
            ko = get_kalshi_open_orders()
            result["kalshi"] = {**kp, "open_orders": ko.get("orders", []), "open_order_count": ko.get("order_count", 0)}
            if kp.get("positions"):
                snapshot_positions(kp["positions"], "kalshi")

        if exchange in ("all", "polymarket"):
            pp = get_polymarket_account()
            result["polymarket"] = {
                "wallet": pp.get("wallet_address"),
                "open_orders": pp.get("open_order_list", []),
                "open_order_count": pp.get("open_orders", 0),
                "recent_trades": pp.get("recent_trade_list", [])[:5],
            }

        if as_json:
            _output(result, True)
        else:
            if "kalshi" in result:
                k = result["kalshi"]
                console.print(f"\n[bold yellow]Kalshi Positions[/bold yellow] ({k.get('position_count', 0)} active)")
                console.print(f"  Total exposure: [green]${k.get('total_exposure_usd', 0):.2f}[/green]")
                console.print(f"  Realized P&L:   [green]${k.get('total_realized_pnl_usd', 0):.2f}[/green]")
                if k.get("positions"):
                    tbl = Table(show_header=True, header_style="bold")
                    tbl.add_column("Ticker", width=28)
                    tbl.add_column("Side", width=6)
                    tbl.add_column("Shares", width=8)
                    tbl.add_column("Exposure $", width=10)
                    tbl.add_column("P&L $", width=8)
                    for p in k["positions"]:
                        pnl_color = "green" if p["realized_pnl_usd"] >= 0 else "red"
                        tbl.add_row(
                            p["ticker"], p["side"],
                            f"{p['position_fp']:.0f}",
                            f"${p['exposure_usd']:.2f}",
                            f"[{pnl_color}]${p['realized_pnl_usd']:.2f}[/{pnl_color}]",
                        )
                    console.print(tbl)
                console.print(f"  Open orders: {k.get('open_order_count', 0)}")

            if "polymarket" in result:
                pp = result["polymarket"]
                console.print(f"\n[bold blue]Polymarket[/bold blue]")
                console.print(f"  Wallet: {pp.get('wallet', 'N/A')}")
                console.print(f"  Open orders: {pp.get('open_order_count', 0)}")
    except Exception as e:
        err = {"status": "error", "error": str(e)}
        if as_json:
            _output(err, True)
        else:
            console.print(f"[red]✗ Positions fetch failed: {e}[/red]")
        sys.exit(1)


# ── order ─────────────────────────────────────────────────────
@cli.command()
@click.option("--exchange", required=True, type=click.Choice(["kalshi", "polymarket"]))
@click.option("--market-id", required=True, help="Market ID or ticker")
@click.option("--side", required=True, type=click.Choice(["yes", "no"]))
@click.option("--price", required=True, type=float, help="Price 0.0–1.0")
@click.option("--size", required=True, type=float, help="USD amount to risk")
@click.option("--ticker", default="", help="Kalshi ticker (required for Kalshi)")
@click.option("--token-id", default="", help="Polymarket YES/NO token ID")
@click.option("--live", "go_live", is_flag=True, help="ACTUALLY place the order (default: dry-run)")
@click.pass_context
def order(ctx, exchange, market_id, side, price, size, ticker, token_id, go_live):
    """
    Place or validate a prediction market order.
    Default is DRY-RUN. Use --live to place a real order.
    """
    as_json = ctx.obj["json"]

    import os
    if go_live:
        os.environ["DRY_RUN"] = "false"
        if not as_json:
            console.print("[bold red]LIVE MODE: real order will be placed![/bold red]")
    else:
        os.environ["DRY_RUN"] = "true"
        if not as_json:
            console.print("[bold yellow]DRY-RUN mode (use --live to place real order)[/bold yellow]")

    try:
        from tools.execution_tool import place_order, validate_order_dry
        from tools.database_tool import insert_order

        # Always validate first
        validation = validate_order_dry(exchange, market_id, side, price, size)
        if not validation["valid"]:
            result = {
                "status": "rejected",
                "violations": validation["violations"],
                "limits": validation["limits"],
            }
            if as_json:
                _output(result, True)
            else:
                console.print(f"[red]✗ Order rejected:[/red]")
                for v in validation["violations"]:
                    console.print(f"  • {v}")
            return

        rec = place_order(
            exchange=exchange,
            market_id=market_id,
            side=side,
            price=price,
            size_usd=size,
            ticker=ticker or market_id,
            token_id=token_id,
        )
        insert_order(rec)

        if as_json:
            _output(rec, True)
        else:
            status_color = {"dry_run": "yellow", "filled": "green", "rejected": "red", "failed": "red"}.get(
                rec["status"], "white"
            )
            console.print(f"[{status_color}]Order status: {rec['status'].upper()}[/{status_color}]")
            if rec["status"] == "filled":
                console.print(f"  Exchange order ID: {rec.get('exchange_order_id')}")
            if rec.get("error"):
                console.print(f"  Error: {rec['error']}")
            console.print(f"  {exchange.upper()} | {market_id} | {side.upper()} | ${size:.2f} @ {price:.3f}")

    except Exception as e:
        err = {"status": "error", "error": str(e)}
        if as_json:
            _output(err, True)
        else:
            console.print(f"[red]✗ Order command failed: {e}[/red]")
        sys.exit(1)


# ── Entry point ───────────────────────────────────────────────
if __name__ == "__main__":
    cli(obj={})
