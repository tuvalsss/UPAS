"""
tools/kalshi_tool.py
Fetch markets from Kalshi API.
Auth: RSA-PSS (SHA256, MAX_LENGTH salt) — NOT PKCS1v15.
Returns standard market objects. All agents use this tool — never call API directly.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from config.variables import KALSHI_API_KEY_ID, KALSHI_BASE, KALSHI_PRIVATE_KEY_PATH
from logging_config.structured_logger import get_logger

logger = get_logger(__name__)


# ── Load RSA private key ──────────────────────────────────────
def _load_private_key():
    key_path = Path(KALSHI_PRIVATE_KEY_PATH)
    if not key_path.exists():
        raise FileNotFoundError(f"Kalshi private key not found: {key_path}")
    with open(key_path, "rb") as f:
        return serialization.load_pem_private_key(f.read(), password=None)


# ── Auth header via RSA-PSS signature ────────────────────────
def _auth_headers(method: str, path: str) -> dict[str, str]:
    ts = str(int(datetime.now(timezone.utc).timestamp() * 1000))
    msg = f"{ts}{method.upper()}{path}".encode()
    private_key = _load_private_key()
    sig = private_key.sign(
        msg,
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
        hashes.SHA256(),
    )
    import base64
    sig_b64 = base64.b64encode(sig).decode()
    return {
        "KALSHI-ACCESS-KEY": KALSHI_API_KEY_ID,
        "KALSHI-ACCESS-TIMESTAMP": ts,
        "KALSHI-ACCESS-SIGNATURE": sig_b64,
        "Content-Type": "application/json",
    }


# ── Normalize Kalshi market to standard schema ────────────────
def _make_market(raw: dict[str, Any]) -> dict[str, Any]:
    # Kalshi API now returns *_dollars fields (already in dollars, 0.0-1.0 range).
    # Legacy *_bid / last_price fields (cents) kept as fallback for old responses.
    def _f(*keys):
        for k in keys:
            v = raw.get(k)
            if v is not None:
                try:
                    return float(v)
                except (TypeError, ValueError):
                    pass
        return 0.0

    yes_bid = _f("yes_bid_dollars")
    yes_ask = _f("yes_ask_dollars")
    last = _f("last_price_dollars", "previous_price_dollars")
    # Prefer mid of bid/ask; fall back to ask, then last, then legacy cents fields.
    if yes_bid > 0 and yes_ask > 0:
        yes_price = (yes_bid + yes_ask) / 2.0
    elif yes_ask > 0:
        yes_price = yes_ask
    elif yes_bid > 0:
        yes_price = yes_bid
    elif last > 0:
        yes_price = last
    else:
        yes_price = _f("yes_bid", "last_price") / 100.0
    no_price = round(1.0 - yes_price, 6) if yes_price > 0 else 0.0
    liquidity = _f("liquidity_dollars", "liquidity") or _f("volume_24h_fp", "volume_fp")
    volume = _f("volume_24h_fp", "volume_fp", "volume")
    # Kalshi often reports liquidity=0 even on active markets.
    # Synthesize a USD liquidity proxy from open_interest × notional (worst case $1/contract)
    # plus top-of-book depth so downstream filters don't wipe Kalshi entirely.
    if liquidity <= 0:
        oi = _f("open_interest_fp", "open_interest")
        notional = _f("notional_value_dollars", "notional_value") or 1.0
        bid_sz = _f("yes_bid_size_fp", "yes_bid_size")
        ask_sz = _f("yes_ask_size_fp", "yes_ask_size")
        yes_bid = _f("yes_bid_dollars")
        yes_ask = _f("yes_ask_dollars")
        depth = bid_sz * yes_bid + ask_sz * (1.0 - yes_ask)
        liquidity = oi * notional + depth
    return {
        "market_id": raw.get("ticker", str(uuid.uuid4())),
        "title": raw.get("title") or raw.get("yes_sub_title") or raw.get("subtitle") or "",
        "source": "kalshi",
        "yes_price": yes_price,
        "no_price": no_price,
        "liquidity": liquidity,
        "volume": volume,
        "expiry_timestamp": raw.get("close_time", raw.get("expiration_time", "")),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "raw": raw,
    }


def fetch_markets(
    status: str = "open",
    limit: int = 100,
    cursor: str = "",
) -> dict[str, Any]:
    """
    Fetch active markets from Kalshi API.
    Returns: { markets: List[MarketObject], cursor: str, error: str | None }
    """
    path = "/trade-api/v2/markets"
    params: dict[str, Any] = {"status": status, "limit": limit}
    if cursor:
        params["cursor"] = cursor

    logger.info("kalshi_tool.fetch_markets", extra={"status": status, "limit": limit})

    try:
        headers = _auth_headers("GET", path)
        resp = requests.get(
            f"{KALSHI_BASE.removesuffix('/trade-api/v2')}{path}",
            headers=headers,
            params=params,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        raw_markets = data.get("markets", [])
        markets = [_make_market(m) for m in raw_markets]
        logger.info(
            "kalshi_tool.fetch_markets.success",
            extra={"count": len(markets)},
        )
        return {
            "markets": markets,
            "cursor": data.get("cursor", ""),
            "error": None,
        }
    except FileNotFoundError as e:
        logger.error("kalshi_tool.key_error", extra={"error": str(e)})
        return {"markets": [], "cursor": "", "error": str(e)}
    except requests.HTTPError as e:
        logger.error("kalshi_tool.http_error", extra={"error": str(e)})
        return {"markets": [], "cursor": "", "error": str(e)}
    except Exception as e:
        logger.error("kalshi_tool.error", extra={"error": str(e)})
        return {"markets": [], "cursor": "", "error": str(e)}


def get_market_by_ticker(ticker: str) -> dict[str, Any]:
    """Fetch a single Kalshi market by ticker."""
    path = f"/trade-api/v2/markets/{ticker}"
    try:
        headers = _auth_headers("GET", path)
        base = KALSHI_BASE.removesuffix("/trade-api/v2")
        resp = requests.get(f"{base}{path}", headers=headers, timeout=10)
        resp.raise_for_status()
        raw = resp.json().get("market", {})
        return {"market": _make_market(raw), "error": None}
    except Exception as e:
        logger.error("kalshi_tool.get_market.error", extra={"error": str(e)})
        return {"market": None, "error": str(e)}


def run(limit: int = 500, max_pages: int = 80, min_non_mve: int = 150) -> dict[str, Any]:
    """Paginate Kalshi until we have ~min_non_mve binary markets (or hit max_pages).
    Kalshi lists MVE combos first — need to scan deep to find real arbitrageable binaries."""
    cursor = ""
    kept: list[dict[str, Any]] = []
    non_mve = 0
    err = None
    for _ in range(max_pages):
        result = fetch_markets(limit=200, cursor=cursor)
        if result.get("error"):
            err = result["error"]; break
        for m in result["markets"]:
            if not (m["yes_price"] > 0 and m["yes_price"] < 1):
                continue
            kept.append(m)
            if not (m.get("market_id") or "").startswith("KXMVE"):
                non_mve += 1
        cursor = result.get("cursor", "")
        if not cursor: break
        if non_mve >= min_non_mve and len(kept) >= limit: break
    # Prioritize non-MVE in the returned slice
    non_mve_list = [m for m in kept if not (m.get("market_id") or "").startswith("KXMVE")]
    mve_list = [m for m in kept if (m.get("market_id") or "").startswith("KXMVE")]
    out = non_mve_list + mve_list
    return {"markets": out[:limit], "source": "kalshi", "count": len(out[:limit]),
            "non_mve": len(non_mve_list), "error": err}
