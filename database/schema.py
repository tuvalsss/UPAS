"""
database/schema.py
SQLite schema definition for all 13 UPAS tables.
Safe additive migrations — never DROP or RENAME.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from config.variables import DATABASE_PATH
from logging_config.structured_logger import get_logger

logger = get_logger(__name__)

_SCHEMA_VERSION = 1

_CREATE_STATEMENTS = [
    # ── markets ─────────────────────────────────────────────
    """CREATE TABLE IF NOT EXISTS markets (
        id                 INTEGER PRIMARY KEY AUTOINCREMENT,
        market_id          TEXT NOT NULL,
        title              TEXT,
        source             TEXT NOT NULL,
        yes_price          REAL,
        no_price           REAL,
        liquidity          REAL,
        volume             REAL,
        expiry_timestamp   TEXT,
        fetched_at         TEXT NOT NULL,
        raw                TEXT,
        token_id_yes       TEXT DEFAULT '',
        token_id_no        TEXT DEFAULT '',
        UNIQUE(market_id, source)
    )""",

    # ── signals ──────────────────────────────────────────────
    """CREATE TABLE IF NOT EXISTS signals (
        signal_id        TEXT PRIMARY KEY,
        market_id        TEXT NOT NULL,
        strategy_name    TEXT NOT NULL,
        direction        TEXT NOT NULL,
        score            REAL,
        confidence       REAL,
        uncertainty      REAL,
        reasoning        TEXT,
        suggested_action TEXT,
        timestamp        TEXT NOT NULL
    )""",

    # ── reverse_signals ──────────────────────────────────────
    """CREATE TABLE IF NOT EXISTS reverse_signals (
        signal_id        TEXT PRIMARY KEY,
        market_id        TEXT NOT NULL,
        strategy_name    TEXT NOT NULL,
        direction        TEXT NOT NULL DEFAULT 'reverse',
        score            REAL,
        confidence       REAL,
        uncertainty      REAL,
        reasoning        TEXT,
        suggested_action TEXT,
        timestamp        TEXT NOT NULL
    )""",

    # ── scores ───────────────────────────────────────────────
    """CREATE TABLE IF NOT EXISTS scores (
        score_id       TEXT PRIMARY KEY,
        signal_id      TEXT NOT NULL,
        ai_score       REAL,
        combined_score REAL,
        confidence     REAL,
        model_used     TEXT,
        timestamp      TEXT NOT NULL
    )""",

    # ── results (realized outcomes) ───────────────────────────
    """CREATE TABLE IF NOT EXISTS results (
        result_id          TEXT PRIMARY KEY,
        signal_id          TEXT NOT NULL,
        market_id          TEXT NOT NULL,
        realized_outcome   INTEGER,
        outcome_timestamp  TEXT
    )""",

    # ── checkpoints ──────────────────────────────────────────
    """CREATE TABLE IF NOT EXISTS checkpoints (
        checkpoint_id   TEXT PRIMARY KEY,
        run_id          TEXT NOT NULL,
        stage           TEXT NOT NULL,
        pipeline_state  TEXT,
        timestamp       TEXT NOT NULL
    )""",

    # ── model_artifacts ──────────────────────────────────────
    """CREATE TABLE IF NOT EXISTS model_artifacts (
        artifact_id    TEXT PRIMARY KEY,
        model_type     TEXT NOT NULL,
        artifact_path  TEXT,
        metrics        TEXT,
        created_at     TEXT NOT NULL
    )""",

    # ── audit_logs (APPEND-ONLY) ──────────────────────────────
    """CREATE TABLE IF NOT EXISTS audit_logs (
        log_id    INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        action    TEXT NOT NULL,
        actor     TEXT,
        details   TEXT
    )""",

    # ── questions_asked (APPEND-ONLY) ─────────────────────────
    """CREATE TABLE IF NOT EXISTS questions_asked (
        question_id   TEXT PRIMARY KEY,
        question_text TEXT NOT NULL,
        context       TEXT,
        asked_at      TEXT NOT NULL,
        answered_at   TEXT,
        answer        TEXT
    )""",

    # ── clarifications ────────────────────────────────────────
    """CREATE TABLE IF NOT EXISTS clarifications (
        clarification_id TEXT PRIMARY KEY,
        question_id      TEXT NOT NULL,
        answer           TEXT,
        timestamp        TEXT NOT NULL
    )""",

    # ── uncertainty_events ────────────────────────────────────
    """CREATE TABLE IF NOT EXISTS uncertainty_events (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp    TEXT NOT NULL,
        confidence   REAL,
        uncertainty  REAL,
        gaps         TEXT,
        conflicts    TEXT,
        stage        TEXT
    )""",

    # ── tool_registry_snapshot ────────────────────────────────
    """CREATE TABLE IF NOT EXISTS tool_registry_snapshot (
        entry_id      INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp     TEXT NOT NULL,
        component     TEXT NOT NULL,
        decision      TEXT NOT NULL,
        existing_tool TEXT,
        reason        TEXT
    )""",

    # ── strategies ────────────────────────────────────────────
    """CREATE TABLE IF NOT EXISTS strategies (
        strategy_name TEXT PRIMARY KEY,
        direction     TEXT NOT NULL,
        enabled       INTEGER DEFAULT 1,
        win_rate      REAL,
        total_signals INTEGER DEFAULT 0,
        last_updated  TEXT
    )""",

    # ── orders ────────────────────────────────────────────────
    """CREATE TABLE IF NOT EXISTS orders (
        order_id          TEXT PRIMARY KEY,
        exchange          TEXT NOT NULL,
        market_id         TEXT NOT NULL,
        side              TEXT NOT NULL,
        price             REAL NOT NULL,
        size_usd          REAL NOT NULL,
        status            TEXT NOT NULL,
        exchange_order_id TEXT,
        dry_run           INTEGER NOT NULL DEFAULT 1,
        error             TEXT,
        timestamp         TEXT NOT NULL
    )""",

    # ── positions ─────────────────────────────────────────────
    """CREATE TABLE IF NOT EXISTS positions (
        id                INTEGER PRIMARY KEY AUTOINCREMENT,
        exchange          TEXT NOT NULL,
        market_id         TEXT NOT NULL,
        ticker            TEXT,
        side              TEXT NOT NULL,
        size_contracts    REAL,
        exposure_usd      REAL,
        total_cost_usd    REAL,
        realized_pnl_usd  REAL DEFAULT 0.0,
        fees_paid_usd     REAL DEFAULT 0.0,
        last_updated      TEXT NOT NULL,
        snapshot_at       TEXT NOT NULL
    )""",

    # ── balances ──────────────────────────────────────────────
    """CREATE TABLE IF NOT EXISTS balances (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        exchange            TEXT NOT NULL,
        cash_balance_usd    REAL,
        portfolio_value_usd REAL,
        total_value_usd     REAL,
        snapshot_at         TEXT NOT NULL
    )""",
]

_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_markets_source ON markets(source, fetched_at)",
    "CREATE INDEX IF NOT EXISTS idx_signals_market ON signals(market_id)",
    "CREATE INDEX IF NOT EXISTS idx_signals_strategy ON signals(strategy_name)",
    "CREATE INDEX IF NOT EXISTS idx_scores_signal ON scores(signal_id)",
    "CREATE INDEX IF NOT EXISTS idx_results_signal ON results(signal_id)",
    "CREATE INDEX IF NOT EXISTS idx_checkpoints_run ON checkpoints(run_id, timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_orders_exchange ON orders(exchange, timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_orders_market ON orders(market_id)",
    "CREATE INDEX IF NOT EXISTS idx_positions_exchange ON positions(exchange, snapshot_at)",
    "CREATE INDEX IF NOT EXISTS idx_balances_exchange ON balances(exchange, snapshot_at)",
]


def _migrate_markets_token_ids(conn: sqlite3.Connection) -> None:
    """Add token_id_yes and token_id_no columns if not present (additive migration)."""
    for col in ("token_id_yes", "token_id_no"):
        try:
            conn.execute(f"ALTER TABLE markets ADD COLUMN {col} TEXT DEFAULT ''")
            logger.info(f"database.migration.markets_add_{col}")
        except sqlite3.OperationalError:
            pass  # Column already exists


def _migrate_markets_unique_constraint(conn: sqlite3.Connection) -> None:
    """
    Migrate markets table from UNIQUE(market_id, source, fetched_at) to
    UNIQUE(market_id, source).  Rebuilds via rename-copy-drop if the old
    constraint is still in place.
    """
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='markets'"
    ).fetchone()
    if not row:
        return  # Table doesn't exist yet — no migration needed
    ddl: str = row[0] or ""
    if "fetched_at" not in ddl:
        return  # Already on the new constraint

    logger.info("database.migration.markets_unique_constraint")
    conn.executescript("""
        ALTER TABLE markets RENAME TO markets_old;

        CREATE TABLE markets (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            market_id          TEXT NOT NULL,
            title              TEXT,
            source             TEXT NOT NULL,
            yes_price          REAL,
            no_price           REAL,
            liquidity          REAL,
            volume             REAL,
            expiry_timestamp   TEXT,
            fetched_at         TEXT NOT NULL,
            raw                TEXT,
            UNIQUE(market_id, source)
        );

        INSERT OR IGNORE INTO markets
            (market_id, title, source, yes_price, no_price, liquidity, volume,
             expiry_timestamp, fetched_at, raw)
        SELECT market_id, title, source, yes_price, no_price, liquidity, volume,
               expiry_timestamp, fetched_at, raw
        FROM markets_old;

        DROP TABLE markets_old;
    """)


def init_database(db_path: Path | None = None) -> None:
    """Create all tables and indexes. Safe to call multiple times (IF NOT EXISTS)."""
    path = db_path or DATABASE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(path))
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        _migrate_markets_unique_constraint(conn)
        _migrate_markets_token_ids(conn)
        for stmt in _CREATE_STATEMENTS:
            conn.execute(stmt)
        for idx in _INDEXES:
            conn.execute(idx)
        conn.commit()
        logger.info("database.schema.init_complete", extra={"db_path": str(path)})
    finally:
        conn.close()


def get_schema_info(db_path: Path | None = None) -> dict:
    """Return info about existing tables."""
    path = db_path or DATABASE_PATH
    if not path.exists():
        return {"exists": False, "tables": []}

    conn = sqlite3.connect(str(path))
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        return {"exists": True, "tables": [r[0] for r in rows]}
    finally:
        conn.close()
