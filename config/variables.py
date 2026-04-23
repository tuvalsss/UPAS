"""
config/variables.py
Python-importable mirror of config/settings.yaml.
All modules import from here — never hardcode values anywhere else.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

# ── Load .env first so env-vars override defaults ─────────────
_ROOT = Path(__file__).parent.parent
load_dotenv(_ROOT / ".env", override=False)

# ── Load settings.yaml ────────────────────────────────────────
_SETTINGS_PATH = Path(__file__).parent / "settings.yaml"
with open(_SETTINGS_PATH, "r", encoding="utf-8") as _f:
    _cfg: dict[str, Any] = yaml.safe_load(_f)


def _get(key: str, default: Any = None) -> Any:
    """Dot-notation access into nested settings dict."""
    parts = key.split(".")
    node = _cfg
    for p in parts:
        if isinstance(node, dict):
            node = node.get(p, default)
        else:
            return default
    return node


# ── Risk & Capital ────────────────────────────────────────────
CAPITAL: float = _get("capital", 1000.0)
RISK_PER_TRADE: float = _get("risk_per_trade", 0.02)

# ── Scanning ──────────────────────────────────────────────────
SCAN_INTERVAL_SECONDS: int = _get("scan_interval_seconds", 60)
YES_PRICE_MIN: float = _get("yes_price_min", 0.05)
YES_PRICE_MAX: float = _get("yes_price_max", 0.95)
LIQUIDITY_MIN: float = _get("liquidity_min", 500)
EXPIRY_HOURS_MAX: int = _get("expiry_hours_max", 168)
IMBALANCE_THRESHOLD: float = _get("imbalance_threshold", 0.15)

# ── Reverse Strategy Thresholds ───────────────────────────────
_rt = _get("reverse_thresholds", {})
REV_PROBABILITY_FREEZE: float = _rt.get("probability_freeze", 0.03)
REV_LIQUIDITY_VACUUM: float = _rt.get("liquidity_vacuum", 200)
REV_CROWD_FATIGUE: float = _rt.get("crowd_fatigue", 0.6)
REV_WHALE_EXHAUSTION: float = _rt.get("whale_exhaustion", 0.8)
REV_FAKE_MOMENTUM: float = _rt.get("fake_momentum", 0.4)
REV_EVENT_SHADOW_DRIFT: float = _rt.get("event_shadow_drift", 0.05)
REV_MIRROR_DIVERGENCE: float = _rt.get("mirror_event_divergence", 0.1)
REV_TIME_PROB_INVERSION: float = _rt.get("time_probability_inversion", 0.07)

# ── Feature Flags ─────────────────────────────────────────────
AI_ENABLED: bool = _get("ai_enabled", True)
ML_ENABLED: bool = _get("ml_enabled", True)
RL_ENABLED: bool = _get("rl_enabled", True)
MCP_ENABLED: bool = _get("mcp_enabled", True)
SKILLS_ENABLED: bool = _get("skills_enabled", True)
SUBAGENTS_ENABLED: bool = _get("subagents_enabled", True)
REVERSE_MODE_ENABLED: bool = _get("reverse_mode_enabled", True)
USE_EXISTING_TOOLS_FIRST: bool = _get("use_existing_tools_first", True)

# ── Anthropic / Claude ────────────────────────────────────────
# CLAUDE_AUTH_MODE: "user" = claude CLI login session, "api" = API key
CLAUDE_AUTH_MODE: str = os.getenv("CLAUDE_AUTH_MODE", _get("claude_auth_mode", "user"))
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL_STANDARD: str = os.getenv(
    "ANTHROPIC_MODEL_STANDARD",
    _get("anthropic_model_standard", "claude-sonnet-4-6"),
)
ANTHROPIC_MODEL_COMPLEX: str = os.getenv(
    "ANTHROPIC_MODEL_COMPLEX",
    _get("anthropic_model_complex", "claude-opus-4-7"),
)
ANTHROPIC_MODEL_FAST: str = os.getenv(
    "ANTHROPIC_MODEL_FAST",
    _get("anthropic_model_fast", "claude-haiku-4-5-20251001"),
)
# Tier A (complex reasoning) → Opus | B (standard scoring) → Sonnet | C (bulk/cheap) → Haiku
ANTHROPIC_TIER_A: str = ANTHROPIC_MODEL_COMPLEX
ANTHROPIC_TIER_B: str = ANTHROPIC_MODEL_STANDARD
ANTHROPIC_TIER_C: str = ANTHROPIC_MODEL_FAST

# Throttle: only call API for signals with rule-based score >= threshold, and top-N per cycle
AI_MIN_SCORE_FOR_API: float = _get("ai_min_score_for_api", 65.0)
AI_MAX_CALLS_PER_CYCLE: int = _get("ai_max_calls_per_cycle", 20)

# ── Checkpointing ─────────────────────────────────────────────
CHECKPOINT_INTERVAL: int = _get("checkpoint_interval", 300)

# ── Logging ───────────────────────────────────────────────────
LOG_LEVEL: str = os.getenv("LOG_LEVEL", _get("log_level", "INFO")).upper()

# ── Uncertainty / Reverse-Thinking ───────────────────────────
ASK_BEFORE_ASSUMING: bool = os.getenv(
    "ASK_BEFORE_ASSUMING",
    str(_get("ask_before_assuming", True)),
).lower() in ("true", "1", "yes")
UNCERTAINTY_THRESHOLD: float = _get("uncertainty_threshold", 0.65)
FALLBACK_TO_USER_QUESTION: bool = _get("fallback_to_user_question", True)

# ── Alert Channels ────────────────────────────────────────────
ALERT_CHANNELS: list[str] = _get("alert_channels", ["console"])
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")

# ── Polymarket ────────────────────────────────────────────────
POLY_GAMMA_BASE: str = os.getenv("POLY_GAMMA_BASE", "https://gamma-api.polymarket.com")
POLY_CLOB_BASE: str = os.getenv("POLY_CLOB_BASE", "https://clob.polymarket.com")
POLY_CLOB_WS: str = os.getenv("POLY_CLOB_WS", "wss://ws-subscriptions-clob.polymarket.com/ws/market")
POLY_API_KEY: str = os.getenv("POLY_API_KEY", "")
POLY_SECRET: str = os.getenv("POLY_SECRET", "")
POLY_PASSPHRASE: str = os.getenv("POLY_PASSPHRASE", "")
POLY_PRIVATE_KEY: str = os.getenv("POLY_PRIVATE_KEY", "")
POLY_BUILDER_API_KEY: str = os.getenv("POLY_BUILDER_API_KEY", "")
POLY_BUILDER_SECRET: str = os.getenv("POLY_BUILDER_SECRET", "")
POLY_BUILDER_PASSPHRASE: str = os.getenv("POLY_BUILDER_PASSPHRASE", "")

# ── Kalshi ────────────────────────────────────────────────────
KALSHI_BASE: str = os.getenv("KALSHI_BASE", "https://api.elections.kalshi.com/trade-api/v2")
KALSHI_API_KEY_ID: str = os.getenv("KALSHI_API_KEY_ID", "")
KALSHI_PRIVATE_KEY_PATH: Path = _ROOT / os.getenv("KALSHI_PRIVATE_KEY_PATH", "config/kalshi_private_key.pem")

# ── Database / Storage ────────────────────────────────────────
DATABASE_PATH: Path = _ROOT / os.getenv("DATABASE_PATH", _get("database_path", "data/upas.db"))
CHECKPOINT_PATH: Path = _ROOT / os.getenv("CHECKPOINT_PATH", _get("checkpoint_path", "data/checkpoints"))

# ── Execution ────────────────────────────────────────────────
DRY_RUN: bool = os.getenv("DRY_RUN", str(_get("dry_run", True))).lower() in ("true", "1", "yes")
MAX_SINGLE_TRADE_USD: float = float(os.getenv("MAX_SINGLE_TRADE_USD", str(_get("max_single_trade_usd", 25.0))))
MAX_POSITION_USD: float = float(os.getenv("MAX_POSITION_USD", str(_get("max_position_usd", 100.0))))
MIN_SIGNAL_SCORE: float = float(_get("min_signal_score", 75.0))
MIN_CONFIDENCE_EXEC: float = float(_get("min_confidence", 0.70))
AUTO_EXECUTE: bool = os.getenv("AUTO_EXECUTE", str(_get("auto_execute", False))).lower() in ("true", "1", "yes")

# ── Derived helpers ───────────────────────────────────────────
def use_api_auth() -> bool:
    """True if we should authenticate Claude via API key (not CLI user session)."""
    return CLAUDE_AUTH_MODE.lower() == "api"


def settings_summary() -> dict[str, Any]:
    """Return a sanitised dict of all settings (no secrets)."""
    return {
        "capital": CAPITAL,
        "risk_per_trade": RISK_PER_TRADE,
        "scan_interval_seconds": SCAN_INTERVAL_SECONDS,
        "ai_enabled": AI_ENABLED,
        "ml_enabled": ML_ENABLED,
        "rl_enabled": RL_ENABLED,
        "claude_auth_mode": CLAUDE_AUTH_MODE,
        "anthropic_model_standard": ANTHROPIC_MODEL_STANDARD,
        "anthropic_model_complex": ANTHROPIC_MODEL_COMPLEX,
        "uncertainty_threshold": UNCERTAINTY_THRESHOLD,
        "reverse_mode_enabled": REVERSE_MODE_ENABLED,
        "log_level": LOG_LEVEL,
        "database_path": str(DATABASE_PATH),
        "checkpoint_path": str(CHECKPOINT_PATH),
    }
