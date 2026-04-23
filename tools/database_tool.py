"""
tools/database_tool.py
SQLite CRUD, deduplication, and safe migrations for UPAS.
All agents use this tool — never write raw SQL from strategy or agent code.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator

from config.variables import DATABASE_PATH
from logging_config.structured_logger import get_logger

logger = get_logger(__name__)

_DB_PATH: Path = DATABASE_PATH


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def _conn() -> Generator[sqlite3.Connection, None, None]:
    """Context manager for SQLite connection with WAL mode."""
    con = sqlite3.connect(str(_DB_PATH), timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


# ── Markets ──────────────────────────────────────────────────
def upsert_market(market: dict[str, Any]) -> bool:
    """
    Insert or refresh a market.  Returns True if a new row was created,
    False if an existing row was updated.  Unique key is (market_id, source).
    """
    sql = """
    INSERT INTO markets
        (market_id, title, source, yes_price, no_price, liquidity, volume,
         expiry_timestamp, fetched_at, raw, token_id_yes, token_id_no)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
    ON CONFLICT(market_id, source) DO UPDATE SET
        yes_price        = excluded.yes_price,
        no_price         = excluded.no_price,
        liquidity        = excluded.liquidity,
        volume           = excluded.volume,
        expiry_timestamp = excluded.expiry_timestamp,
        fetched_at       = excluded.fetched_at,
        raw              = excluded.raw,
        token_id_yes     = CASE WHEN excluded.token_id_yes != '' THEN excluded.token_id_yes ELSE token_id_yes END,
        token_id_no      = CASE WHEN excluded.token_id_no != '' THEN excluded.token_id_no ELSE token_id_no END
    """
    with _conn() as con:
        cur = con.execute(sql, (
            market["market_id"], market.get("title", ""), market["source"],
            market["yes_price"], market["no_price"], market["liquidity"],
            market["volume"], market["expiry_timestamp"], market["fetched_at"],
            json.dumps(market.get("raw", {})),
            market.get("token_id_yes", ""),
            market.get("token_id_no", ""),
        ))
        inserted = cur.rowcount > 0
    logger.debug("db.upsert_market", extra={"market_id": market["market_id"], "inserted": inserted})
    return inserted


def get_market(market_id: str, source: str) -> dict[str, Any] | None:
    with _conn() as con:
        row = con.execute(
            "SELECT * FROM markets WHERE market_id=? AND source=? ORDER BY fetched_at DESC LIMIT 1",
            (market_id, source),
        ).fetchone()
    return dict(row) if row else None


def get_recent_markets(limit: int = 500) -> list[dict[str, Any]]:
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM markets ORDER BY fetched_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


# ── Signals ──────────────────────────────────────────────────
def insert_signal(signal: dict[str, Any]) -> None:
    table = "reverse_signals" if signal.get("direction") == "reverse" else "signals"
    sql = f"""
    INSERT OR REPLACE INTO {table}
        (signal_id, market_id, strategy_name, direction, score, confidence,
         uncertainty, reasoning, suggested_action, timestamp)
    VALUES (?,?,?,?,?,?,?,?,?,?)
    """
    with _conn() as con:
        con.execute(sql, (
            signal["signal_id"], signal["market_id"], signal["strategy_name"],
            signal["direction"], signal["score"], signal["confidence"],
            signal["uncertainty"], signal["reasoning"],
            signal["suggested_action"], signal["timestamp"],
        ))
    logger.debug("db.insert_signal", extra={"signal_id": signal["signal_id"]})


def get_signals(market_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    if market_id:
        with _conn() as con:
            rows = con.execute(
                "SELECT * FROM signals WHERE market_id=? ORDER BY timestamp DESC LIMIT ?",
                (market_id, limit),
            ).fetchall()
    else:
        with _conn() as con:
            rows = con.execute(
                "SELECT * FROM signals ORDER BY timestamp DESC LIMIT ?", (limit,)
            ).fetchall()
    return [dict(r) for r in rows]


def get_signal_by_id(signal_id: str) -> dict[str, Any] | None:
    with _conn() as con:
        row = con.execute("SELECT * FROM signals WHERE signal_id=?", (signal_id,)).fetchone()
    return dict(row) if row else None


def get_score_by_signal_id(signal_id: str) -> dict[str, Any] | None:
    """Return the latest score record for a signal, or None."""
    with _conn() as con:
        row = con.execute(
            "SELECT * FROM scores WHERE signal_id=? ORDER BY timestamp DESC LIMIT 1",
            (signal_id,),
        ).fetchone()
    return dict(row) if row else None


# ── Scores ───────────────────────────────────────────────────
def insert_score(score: dict[str, Any]) -> None:
    sql = """
    INSERT OR REPLACE INTO scores
        (score_id, signal_id, ai_score, combined_score, confidence, model_used, timestamp)
    VALUES (?,?,?,?,?,?,?)
    """
    with _conn() as con:
        con.execute(sql, (
            score["score_id"], score["signal_id"], score["ai_score"],
            score["combined_score"], score["confidence"],
            score.get("model_used", ""), score["timestamp"],
        ))


# ── Checkpoints ──────────────────────────────────────────────
def save_checkpoint(checkpoint: dict[str, Any]) -> None:
    sql = """
    INSERT OR REPLACE INTO checkpoints
        (checkpoint_id, run_id, stage, pipeline_state, timestamp)
    VALUES (?,?,?,?,?)
    """
    with _conn() as con:
        con.execute(sql, (
            checkpoint["checkpoint_id"], checkpoint["run_id"],
            checkpoint["stage"], json.dumps(checkpoint.get("pipeline_state", {})),
            checkpoint.get("timestamp", _now()),
        ))
    logger.info("db.save_checkpoint", extra={"stage": checkpoint["stage"]})


def get_latest_checkpoint() -> dict[str, Any] | None:
    with _conn() as con:
        row = con.execute(
            "SELECT * FROM checkpoints ORDER BY timestamp DESC LIMIT 1"
        ).fetchone()
    if row:
        d = dict(row)
        d["pipeline_state"] = json.loads(d.get("pipeline_state") or "{}")
        return d
    return None


# ── Audit log (append-only) ───────────────────────────────────
def append_audit_log(action: str, actor: str, details: dict[str, Any]) -> None:
    with _conn() as con:
        con.execute(
            "INSERT INTO audit_logs (timestamp, action, actor, details) VALUES (?,?,?,?)",
            (_now(), action, actor, json.dumps(details)),
        )


# ── Questions (append-only) ───────────────────────────────────
def append_question(question_id: str, text: str, context: dict[str, Any]) -> None:
    with _conn() as con:
        con.execute(
            "INSERT INTO questions_asked (question_id, question_text, context, asked_at) VALUES (?,?,?,?)",
            (question_id, text, json.dumps(context), _now()),
        )


def record_answer(question_id: str, answer: str) -> None:
    with _conn() as con:
        con.execute(
            "UPDATE questions_asked SET answered_at=?, answer=? WHERE question_id=?",
            (_now(), answer, question_id),
        )


# ── Uncertainty events ───────────────────────────────────────
def log_uncertainty_event(event: dict[str, Any]) -> None:
    with _conn() as con:
        con.execute(
            "INSERT INTO uncertainty_events (timestamp, confidence, uncertainty, gaps, conflicts, stage) VALUES (?,?,?,?,?,?)",
            (
                _now(),
                event.get("confidence", 0.0),
                event.get("uncertainty", 0.0),
                json.dumps(event.get("gaps", [])),
                json.dumps(event.get("conflicts", [])),
                event.get("stage", ""),
            ),
        )


# ── Tool registry snapshot ────────────────────────────────────
def log_tool_decision(component: str, decision: str, existing_tool: str | None, reason: str) -> None:
    with _conn() as con:
        con.execute(
            "INSERT INTO tool_registry_snapshot (timestamp, component, decision, existing_tool, reason) VALUES (?,?,?,?,?)",
            (_now(), component, decision, existing_tool or "", reason),
        )


# ── Results ───────────────────────────────────────────────────
def insert_result(result: dict[str, Any]) -> None:
    sql = """
    INSERT OR REPLACE INTO results
        (result_id, signal_id, market_id, realized_outcome, outcome_timestamp)
    VALUES (?,?,?,?,?)
    """
    with _conn() as con:
        con.execute(sql, (
            result["result_id"], result["signal_id"], result["market_id"],
            result.get("realized_outcome"), result.get("outcome_timestamp", _now()),
        ))


def get_results_for_training(min_count: int = 50) -> list[dict[str, Any]]:
    """Returns resolved outcomes for ML training (realized_outcome is not null)."""
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM results WHERE realized_outcome IS NOT NULL ORDER BY outcome_timestamp DESC"
        ).fetchall()
    return [dict(r) for r in rows]


# ── Orders ───────────────────────────────────────────────────
def insert_order(order: dict[str, Any]) -> None:
    sql = """
    INSERT OR REPLACE INTO orders
        (order_id, exchange, market_id, side, price, size_usd, status,
         exchange_order_id, dry_run, error, timestamp, paper_trade)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
    """
    with _conn() as con:
        con.execute(sql, (
            order["order_id"], order["exchange"], order["market_id"],
            order["side"], order["price"], order["size_usd"],
            order["status"], order.get("exchange_order_id", ""),
            1 if order.get("dry_run", True) else 0,
            order.get("error"), order["timestamp"],
            1 if order.get("paper_trade") else 0,
        ))
    logger.debug("db.insert_order", extra={"order_id": order["order_id"], "status": order["status"]})


def get_orders(exchange: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    with _conn() as con:
        if exchange:
            rows = con.execute(
                "SELECT * FROM orders WHERE exchange=? ORDER BY timestamp DESC LIMIT ?",
                (exchange, limit),
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT * FROM orders ORDER BY timestamp DESC LIMIT ?", (limit,)
            ).fetchall()
    return [dict(r) for r in rows]


# ── Positions snapshot ────────────────────────────────────────
def snapshot_positions(positions: list[dict[str, Any]], exchange: str) -> None:
    """Replace the positions snapshot for the given exchange (atomic refresh)."""
    now = _now()
    with _conn() as con:
        con.execute("DELETE FROM positions WHERE exchange=?", (exchange,))
        for p in positions:
            con.execute(
                """INSERT INTO positions
                    (exchange, market_id, ticker, side, size_contracts, exposure_usd,
                     total_cost_usd, realized_pnl_usd, fees_paid_usd, last_updated, snapshot_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    exchange,
                    p.get("market_id") or p.get("ticker") or p.get("token_id") or "",
                    p.get("ticker") or (p.get("title", "")[:64]),
                    p.get("side") or p.get("outcome", ""),
                    p.get("position_fp", p.get("size_contracts", p.get("size", 0))),
                    p.get("exposure_usd", p.get("value_usd", 0)),
                    p.get("total_cost_usd", p.get("total_cost_dollars", p.get("avg_price", 0) * p.get("size", 0))),
                    p.get("realized_pnl_usd", 0),
                    p.get("fees_paid_usd", 0),
                    p.get("last_updated", now),
                    now,
                ),
            )
    logger.info("db.snapshot_positions", extra={"exchange": exchange, "count": len(positions)})


# ── Balance snapshots ─────────────────────────────────────────
def snapshot_balance(exchange: str, cash_usd: float, portfolio_usd: float) -> None:
    with _conn() as con:
        con.execute(
            """INSERT INTO balances (exchange, cash_balance_usd, portfolio_value_usd, total_value_usd, snapshot_at)
               VALUES (?,?,?,?,?)""",
            (exchange, cash_usd, portfolio_usd, cash_usd + portfolio_usd, _now()),
        )
    logger.info("db.snapshot_balance", extra={"exchange": exchange, "total": cash_usd + portfolio_usd})


# ── Market lookup (any source) ───────────────────────────────
def get_market_by_market_id(market_id: str) -> dict[str, Any] | None:
    """Return the most recently fetched market row for market_id, any source."""
    with _conn() as con:
        row = con.execute(
            "SELECT * FROM markets WHERE market_id=? ORDER BY fetched_at DESC LIMIT 1",
            (market_id,),
        ).fetchone()
    return dict(row) if row else None


def get_recent_orders(hours: int = 24) -> list[dict[str, Any]]:
    """Return orders placed within the last N hours (for duplicate prevention)."""
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM orders WHERE timestamp >= ? ORDER BY timestamp DESC",
            (cutoff.isoformat(),),
        ).fetchall()
    return [dict(r) for r in rows]


# ── Export ────────────────────────────────────────────────────
def export_signals(limit: int = 1000) -> list[dict[str, Any]]:
    with _conn() as con:
        rows = con.execute(
            """SELECT s.*, sc.ai_score, sc.combined_score
               FROM signals s
               LEFT JOIN scores sc ON s.signal_id = sc.signal_id
               ORDER BY s.timestamp DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]
