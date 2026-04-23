"""
tools/polymarket_tool.py
Fetch markets from Polymarket CLOB API.
Returns standard market objects. All agents use this tool — never call API directly.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

import requests

from config.variables import (
    POLY_API_KEY,
    POLY_CLOB_BASE,
    POLY_GAMMA_BASE,
    POLY_PASSPHRASE,
    POLY_SECRET,
)
from logging_config.structured_logger import get_logger

logger = get_logger(__name__)

# ── Standard market object ──────────────────────────────────
def _make_market(raw: dict[str, Any], source: str = "polymarket") -> dict[str, Any]:
    """Normalize raw Polymarket CLOB/Gamma market to standard schema.

    Gamma API uses camelCase keys; CLOB API uses snake_case.
    """
    # market_id: Gamma → conditionId, CLOB → condition_id
    market_id = str(
        raw.get("conditionId")
        or raw.get("condition_id")
        or raw.get("id")
        or str(uuid.uuid4())
    )

    # yes_price: Gamma → outcomePrices[0] (JSON-encoded string); fallback → bestBid
    outcome_prices = raw.get("outcomePrices") or []
    if isinstance(outcome_prices, str):
        try:
            outcome_prices = json.loads(outcome_prices)
        except (ValueError, TypeError):
            outcome_prices = []
    try:
        yes_price = float(outcome_prices[0]) if outcome_prices else float(
            raw.get("bestBid") or raw.get("best_bid") or 0.0
        )
    except (ValueError, TypeError, IndexError):
        yes_price = 0.0

    no_price = round(1.0 - yes_price, 6)

    # liquidity: Gamma → liquidityNum; CLOB → liquidity
    liquidity = float(raw.get("liquidityNum") or raw.get("liquidity") or 0.0)

    # volume: prefer plain volume, then 24hr variant
    volume = float(raw.get("volume") or raw.get("volume24hr") or 0.0)

    # expiry: Gamma → endDateIso or endDate; CLOB → end_date_iso or endDate
    expiry = (
        raw.get("endDateIso")
        or raw.get("endDate")
        or raw.get("end_date_iso")
        or ""
    )

    # CLOB token IDs: Gamma returns clobTokenIds as a JSON-encoded string
    # index 0 = YES token, index 1 = NO token
    clob_ids = raw.get("clobTokenIds") or "[]"
    if isinstance(clob_ids, str):
        try:
            clob_ids = json.loads(clob_ids)
        except (ValueError, TypeError):
            clob_ids = []
    token_id_yes = str(clob_ids[0]) if len(clob_ids) > 0 else ""
    token_id_no = str(clob_ids[1]) if len(clob_ids) > 1 else ""

    return {
        "market_id": market_id,
        "title": raw.get("question", raw.get("market_slug", "")),
        "source": source,
        "yes_price": yes_price,
        "no_price": no_price,
        "liquidity": liquidity,
        "volume": volume,
        "expiry_timestamp": expiry,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "token_id_yes": token_id_yes,
        "token_id_no": token_id_no,
        "raw": raw,
    }


# ── CLOB Auth headers ────────────────────────────────────────
def _clob_headers() -> dict[str, str]:
    return {
        "POLY-API-KEY": POLY_API_KEY,
        "POLY-SECRET": POLY_SECRET,
        "POLY-PASSPHRASE": POLY_PASSPHRASE,
        "Content-Type": "application/json",
    }


# ── Fetch from CLOB markets endpoint ────────────────────────
def fetch_clob_markets(
    limit: int = 100,
    next_cursor: str = "",
) -> dict[str, Any]:
    """
    Fetch active markets from Polymarket CLOB API.
    Returns: { markets: List[MarketObject], next_cursor: str, error: str | None }
    """
    url = f"{POLY_CLOB_BASE}/markets"
    params: dict[str, Any] = {"limit": limit}
    if next_cursor:
        params["next_cursor"] = next_cursor

    logger.info("polymarket_tool.fetch_clob", extra={"url": url, "limit": limit})

    try:
        resp = requests.get(url, headers=_clob_headers(), params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        raw_markets = data.get("data", [])
        markets = [_make_market(m) for m in raw_markets]
        logger.info(
            "polymarket_tool.fetch_clob.success",
            extra={"count": len(markets), "next_cursor": data.get("next_cursor", "")},
        )
        return {
            "markets": markets,
            "next_cursor": data.get("next_cursor", ""),
            "error": None,
        }
    except requests.HTTPError as e:
        logger.error("polymarket_tool.fetch_clob.http_error", extra={"error": str(e)})
        return {"markets": [], "next_cursor": "", "error": str(e)}
    except Exception as e:
        logger.error("polymarket_tool.fetch_clob.error", extra={"error": str(e)})
        return {"markets": [], "next_cursor": "", "error": str(e)}


def fetch_gamma_markets(limit: int = 100) -> dict[str, Any]:
    """
    Fetch active markets from Polymarket Gamma API (metadata, no auth required).
    Returns: { markets: List[MarketObject], error: str | None }
    """
    url = f"{POLY_GAMMA_BASE}/markets"
    # Sort by closest-ending first so we prioritize same-day / this-week markets
    # (Gamma supports order=endDate&ascending=true)
    params = {
        "limit": limit,
        "active": "true",
        "closed": "false",
        "order": "endDate",
        "ascending": "true",
        "end_date_min": datetime.now(timezone.utc).isoformat(),
    }

    logger.info("polymarket_tool.fetch_gamma", extra={"url": url})

    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        raw_markets = resp.json()
        markets = [_make_market(m) for m in raw_markets]
        logger.info("polymarket_tool.fetch_gamma.success", extra={"count": len(markets)})
        return {"markets": markets, "error": None}
    except Exception as e:
        logger.error("polymarket_tool.fetch_gamma.error", extra={"error": str(e)})
        return {"markets": [], "error": str(e)}


def get_market_by_id(condition_id: str) -> dict[str, Any]:
    """Fetch a single market by condition_id from CLOB."""
    url = f"{POLY_CLOB_BASE}/markets/{condition_id}"
    try:
        resp = requests.get(url, headers=_clob_headers(), timeout=10)
        resp.raise_for_status()
        raw = resp.json()
        return {"market": _make_market(raw), "error": None}
    except Exception as e:
        logger.error("polymarket_tool.get_market.error", extra={"error": str(e)})
        return {"market": None, "error": str(e)}


def run(limit: int = 100) -> dict[str, Any]:
    """
    Main entry point. Fetches markets via Gamma API (real liquidity data).
    Falls back to CLOB API if Gamma fails.
    Returns: { markets: List[MarketObject], source: "polymarket", error: str | None }
    """
    result = fetch_gamma_markets(limit=limit)
    if result["error"] or not result["markets"]:
        logger.warning(
            "polymarket_tool.gamma_fallback",
            extra={"error": result["error"]},
        )
        result = fetch_clob_markets(limit=limit)
    return {
        "markets": result["markets"],
        "source": "polymarket",
        "count": len(result["markets"]),
        "error": result["error"],
    }
