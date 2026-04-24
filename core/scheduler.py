"""
core/scheduler.py
Continuous scan mode with exponential backoff, configurable interval,
and graceful Windows shutdown (Ctrl+C safe).
"""
from __future__ import annotations

import signal
import sys
import time
from typing import Any

from config.variables import CHECKPOINT_INTERVAL, SCAN_INTERVAL_SECONDS
from tools.checkpoint_tool import save as save_checkpoint
from logging_config.structured_logger import get_logger

logger = get_logger(__name__)

_running = True
_current_state: dict[str, Any] = {}


def _shutdown_handler(sig, frame) -> None:
    """Graceful Windows Ctrl+C handler — saves checkpoint before exit."""
    global _running
    _running = False
    logger.info("scheduler.shutdown_signal", extra={"signal": sig})
    if _current_state:
        try:
            save_checkpoint("shutdown", _current_state)
            print("\n[UPAS] Checkpoint saved. Shutting down gracefully.")
        except Exception:
            print("\n[UPAS] Shutdown — could not save checkpoint.")
    sys.exit(0)


signal.signal(signal.SIGINT, _shutdown_handler)
if hasattr(signal, "SIGTERM"):
    signal.signal(signal.SIGTERM, _shutdown_handler)


def _sync_account_state() -> None:
    """Snapshot live balances and positions to DB (best-effort, never raises)."""
    try:
        from tools.account_tool import (
            get_kalshi_balance,
            get_kalshi_positions,
            get_polymarket_account,
            get_polymarket_positions,
        )
        from tools.database_tool import snapshot_balance, snapshot_positions

        kb = get_kalshi_balance()
        if not kb.get("error"):
            snapshot_balance("kalshi", kb["cash_balance_usd"], kb["portfolio_value_usd"])

        kp = get_kalshi_positions()
        if not kp.get("error") and kp.get("positions"):
            snapshot_positions(kp["positions"], "kalshi")

        pa = get_polymarket_account()
        if not pa.get("error"):
            # snapshot_balance computes total = cash + positions, so pass positions-only
            # (portfolio_value_usd already includes cash — would double-count)
            snapshot_balance(
                "polymarket",
                pa.get("cash_balance_usd", 0.0),
                pa.get("positions_value_usd", 0.0),
            )

        pp = get_polymarket_positions()
        if not pp.get("error") and pp.get("positions"):
            snapshot_positions(pp["positions"], "polymarket")

        logger.info("scheduler.account_sync.done")
    except Exception as e:
        logger.warning("scheduler.account_sync.error", extra={"error": str(e)})


def run_continuous(
    verbose: bool = False,
    strict: bool = False,
    non_interactive: bool = False,
) -> None:
    """
    Run the pipeline continuously with exponential backoff on errors.
    Stops on Ctrl+C — saves checkpoint before exit.
    """
    global _running, _current_state
    _running = True

    from core.engine import run_pipeline

    consecutive_errors = 0
    max_backoff = 600  # 10 minutes cap
    interval = SCAN_INTERVAL_SECONDS
    last_checkpoint_time = time.time()

    logger.info("scheduler.start", extra={"interval": interval})
    print(f"[UPAS] Live mode started — scanning every {interval}s. Press Ctrl+C to stop.")

    while _running:
        try:
            result = run_pipeline(
                verbose=verbose,
                strict=strict,
                non_interactive=non_interactive,
            )
            _current_state = result
            consecutive_errors = 0
            interval = SCAN_INTERVAL_SECONDS  # Reset to base interval on success

            logger.info("scheduler.pass_complete", extra={
                "markets": result.get("markets_scanned"),
                "signals": result.get("signals_generated"),
                "ranked": len(result.get("ranked_signals", [])),
            })

            # Periodic checkpoint + account sync
            now = time.time()
            if now - last_checkpoint_time >= CHECKPOINT_INTERVAL:
                save_checkpoint("scheduler_periodic", _current_state)
                last_checkpoint_time = now
                _sync_account_state()

        except Exception as e:
            consecutive_errors += 1
            backoff = min(max_backoff, interval * (2 ** min(consecutive_errors, 5)))
            logger.error("scheduler.pass_error", extra={
                "error": str(e),
                "consecutive_errors": consecutive_errors,
                "backoff_s": backoff,
            })
            print(f"[UPAS] Error #{consecutive_errors}: {e}. Backing off {backoff:.0f}s.")
            time.sleep(backoff)
            continue

        # Wait for next interval (check _running each second)
        for _ in range(int(interval)):
            if not _running:
                break
            time.sleep(1)


if __name__ == "__main__":
    import argparse

    # License gate — runs before the loop starts. If LICENSE_REQUIRED=1 and
    # license.jwt is invalid/expired/revoked, the process exits non-zero.
    # Default (LICENSE_REQUIRED=0) logs a WARN and continues — open-source mode.
    try:
        from core.license_guard import guard_or_exit
        lic = guard_or_exit()
        logger.info("scheduler.license_ok", extra={
            "email": lic.get("email"), "plan": lic.get("plan"),
            "is_admin": lic.get("is_admin", False),
            "expiry": lic.get("expiry"),
        })
    except Exception as _e:
        logger.warning("scheduler.license_check_error", extra={"error": str(_e)})

    p = argparse.ArgumentParser(description="UPAS continuous scheduler")
    p.add_argument("--verbose", action="store_true")
    p.add_argument("--strict", action="store_true")
    p.add_argument("--non-interactive", action="store_true",
                   help="Never ask questions — run fully autonomous")
    args = p.parse_args()
    run_continuous(
        verbose=args.verbose,
        strict=args.strict,
        non_interactive=args.non_interactive,
    )
