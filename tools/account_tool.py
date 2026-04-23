"""
tools/account_tool.py
Read-only account state: balances, positions, open orders for Polymarket and Kalshi.
Never places orders — purely fetches account data.
"""
from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from typing import Any

import requests

from config.variables import (
    KALSHI_API_KEY_ID,
    KALSHI_BASE,
    KALSHI_PRIVATE_KEY_PATH,
    POLY_API_KEY,
    POLY_CLOB_BASE,
    POLY_PASSPHRASE,
    POLY_PRIVATE_KEY,
    POLY_SECRET,
)
from logging_config.structured_logger import get_logger

logger = get_logger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Kalshi auth (RSA-PSS) ────────────────────────────────────
def _kalshi_headers(method: str, path: str) -> dict[str, str]:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    from pathlib import Path

    ts = str(int(datetime.now(timezone.utc).timestamp() * 1000))
    with open(Path(KALSHI_PRIVATE_KEY_PATH), "rb") as f:
        key = serialization.load_pem_private_key(f.read(), password=None)
    msg = f"{ts}{method.upper()}{path}".encode()
    sig = base64.b64encode(
        key.sign(
            msg,
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
            hashes.SHA256(),
        )
    ).decode()
    return {
        "KALSHI-ACCESS-KEY": KALSHI_API_KEY_ID,
        "KALSHI-ACCESS-TIMESTAMP": ts,
        "KALSHI-ACCESS-SIGNATURE": sig,
        "Content-Type": "application/json",
    }


def _kalshi_get(path: str, params: dict | None = None) -> dict[str, Any]:
    base = KALSHI_BASE.removesuffix("/trade-api/v2")
    try:
        r = requests.get(
            f"{base}{path}",
            headers=_kalshi_headers("GET", path),
            params=params or {},
            timeout=15,
        )
        r.raise_for_status()
        return {"data": r.json(), "error": None}
    except Exception as e:
        logger.error("account_tool.kalshi_get.error", extra={"path": path, "error": str(e)})
        return {"data": {}, "error": str(e)}


# ── Polymarket ClobClient ────────────────────────────────────
def _poly_client():
    from py_clob_client.client import ClobClient
    from py_clob_client.clob_types import ApiCreds
    from py_clob_client.constants import POLYGON
    return ClobClient(
        host=POLY_CLOB_BASE,
        chain_id=POLYGON,
        key=POLY_PRIVATE_KEY,
        creds=ApiCreds(api_key=POLY_API_KEY, api_secret=POLY_SECRET, api_passphrase=POLY_PASSPHRASE),
    )


# ── Public API ───────────────────────────────────────────────

def get_kalshi_balance() -> dict[str, Any]:
    """Return Kalshi cash balance and portfolio value in USD."""
    result = _kalshi_get("/trade-api/v2/portfolio/balance")
    if result["error"]:
        return {"exchange": "kalshi", "error": result["error"]}
    raw = result["data"]
    # Kalshi returns balance in cents
    return {
        "exchange": "kalshi",
        "cash_balance_usd": round(raw.get("balance", 0) / 100, 2),
        "portfolio_value_usd": round(raw.get("portfolio_value", 0) / 100, 2),
        "total_value_usd": round((raw.get("balance", 0) + raw.get("portfolio_value", 0)) / 100, 2),
        "raw": raw,
        "timestamp": _now(),
        "error": None,
    }


def get_kalshi_positions() -> dict[str, Any]:
    """Return all Kalshi market positions with exposure and P&L."""
    result = _kalshi_get("/trade-api/v2/portfolio/positions", params={"limit": 200})
    if result["error"]:
        return {"exchange": "kalshi", "positions": [], "error": result["error"]}

    raw = result["data"]
    market_positions = raw.get("market_positions", [])
    active = [
        {
            "ticker": p["ticker"],
            "position_fp": float(p.get("position_fp", 0)),
            "exposure_usd": float(p.get("market_exposure_dollars", 0)),
            "total_cost_usd": float(p.get("total_traded_dollars", 0)),
            "realized_pnl_usd": float(p.get("realized_pnl_dollars", 0)),
            "fees_paid_usd": float(p.get("fees_paid_dollars", 0)),
            "side": "long" if float(p.get("position_fp", 0)) > 0 else "short",
            "last_updated": p.get("last_updated_ts", ""),
        }
        for p in market_positions
        if float(p.get("position_fp", 0)) != 0
    ]

    total_exposure = sum(p["exposure_usd"] for p in active)
    total_pnl = sum(p["realized_pnl_usd"] for p in active)

    logger.info("account_tool.kalshi_positions", extra={"active": len(active), "exposure": total_exposure})
    return {
        "exchange": "kalshi",
        "positions": active,
        "total_exposure_usd": round(total_exposure, 2),
        "total_realized_pnl_usd": round(total_pnl, 2),
        "position_count": len(active),
        "timestamp": _now(),
        "error": None,
    }


def get_kalshi_open_orders() -> dict[str, Any]:
    """Return all resting (open) Kalshi orders."""
    result = _kalshi_get("/trade-api/v2/portfolio/orders", params={"status": "resting", "limit": 100})
    if result["error"]:
        return {"exchange": "kalshi", "orders": [], "error": result["error"]}
    orders = result["data"].get("orders", [])
    return {
        "exchange": "kalshi",
        "orders": orders,
        "order_count": len(orders),
        "timestamp": _now(),
        "error": None,
    }


def _get_poly_proxy_address(client) -> str:
    """Return the proxy wallet for this Polymarket account.
    Priority: POLY_FUNDER_ADDRESS env → Polymarket profile API → EOA fallback.
    """
    import os
    env_proxy = os.getenv("POLY_FUNDER_ADDRESS", "").strip()
    if env_proxy:
        return env_proxy
    eoa = client.get_address()
    api_proxy = _get_poly_proxy_address_via_api(eoa)
    if api_proxy:
        return api_proxy
    try:
        trades = client.get_trades() or []
        for t in trades:
            ma = t.get("maker_address", "")
            if ma and ma.lower() != eoa.lower():
                return ma
    except Exception:
        pass
    return eoa


def get_polymarket_positions() -> dict[str, Any]:
    """
    Fetch Polymarket open positions via the public data API.
    Must query with the proxy wallet address (not the EOA) because
    Polymarket indexes positions and balances under the proxy contract.
    Falls back to empty list on failure — never raises.
    """
    try:
        client = _poly_client()
        proxy_address = _get_poly_proxy_address(client)

        resp = requests.get(
            "https://data-api.polymarket.com/positions",
            params={"user": proxy_address, "sizeThreshold": "0"},
            timeout=15,
        )
        resp.raise_for_status()
        raw_positions = resp.json() if isinstance(resp.json(), list) else []

        positions = []
        portfolio_value = 0.0

        for p in raw_positions:
            current_price = float(p.get("curPrice", p.get("currentPrice", 0)) or 0)
            size = float(p.get("size", p.get("amount", 0)) or 0)
            # Trust Polymarket's per-position currentValue (matches UI), fall back to size*price
            value_usd = float(p.get("currentValue", size * current_price) or 0)
            redeemable = bool(p.get("redeemable", False))
            # Redeemable losers have value 0; only count real live/tradable value
            portfolio_value += value_usd

            positions.append({
                "token_id": p.get("asset", p.get("token_id", "")),
                "title": p.get("title", p.get("question", ""))[:80],
                "outcome": p.get("outcome", ""),
                "size": round(size, 4),
                "current_price": round(current_price, 6),
                "value_usd": round(value_usd, 2),
                "avg_price": round(float(p.get("avgPrice", p.get("average_price", 0)) or 0), 6),
                "unrealized_pnl_usd": round(float(p.get("cashPnl", p.get("unrealizedPnl", 0)) or 0), 2),
                "redeemable": redeemable,
            })

        logger.info("account_tool.polymarket_positions", extra={
            "positions": len(positions), "portfolio_value": round(portfolio_value, 2),
        })
        return {
            "exchange": "polymarket",
            "positions": positions,
            "portfolio_value_usd": round(portfolio_value, 2),
            "position_count": len(positions),
            "timestamp": _now(),
            "error": None,
        }
    except Exception as e:
        logger.error("account_tool.polymarket_positions.error", extra={"error": str(e)})
        return {"exchange": "polymarket", "positions": [], "portfolio_value_usd": 0.0, "error": str(e)}


def get_polymarket_account() -> dict[str, Any]:
    """Return Polymarket wallet address, open orders, recent fills, and portfolio value."""
    try:
        client = _poly_client()
        address = client.get_address()

        # Open orders
        try:
            orders = client.get_orders() or []
        except Exception:
            orders = []

        # Recent trades (last 20)
        try:
            trades = client.get_trades() or []
            trades = trades[:20]
        except Exception:
            trades = []

        # USDC cash balance held on the Polymarket proxy wallet.
        # signature_type=1 (POLY_PROXY) is REQUIRED — default (-1/EOA) returns the signer's
        # EOA balance, which is always 0 since Polymarket keeps funds on the proxy.
        try:
            from py_clob_client.clob_types import BalanceAllowanceParams, AssetType
            bal_raw = client.get_balance_allowance(
                BalanceAllowanceParams(asset_type=AssetType.COLLATERAL, signature_type=1)
            )
            usdc_balance = float(bal_raw.get("balance", 0)) / 1e6
        except Exception:
            usdc_balance = 0.0

        # Proxy wallet address (where positions/funds actually live)
        proxy_address = _get_poly_proxy_address(client)

        # Portfolio value from positions API (uses proxy address)
        positions_data = get_polymarket_positions()
        portfolio_value = positions_data.get("portfolio_value_usd", 0.0)

        # Total = cash (proxy USDC) + positions value. Matches the UI "Portfolio" figure.
        total_value = round(usdc_balance + portfolio_value, 2)

        logger.info("account_tool.polymarket_account", extra={
            "address": address, "proxy": proxy_address,
            "orders": len(orders), "trades": len(trades),
            "portfolio_value": portfolio_value,
        })
        return {
            "exchange": "polymarket",
            "wallet_address": address,
            "proxy_wallet": proxy_address,
            "usdc_balance": round(usdc_balance, 2),
            "cash_balance_usd": round(usdc_balance, 2),
            "available_to_trade_usd": round(usdc_balance, 2),
            "positions_value_usd": round(portfolio_value, 2),
            "portfolio_value_usd": total_value,
            "total_value_usd": total_value,
            "open_orders": len(orders),
            "open_order_list": orders,
            "recent_trades": len(trades),
            "recent_trade_list": trades,
            "timestamp": _now(),
            "error": None,
        }
    except Exception as e:
        logger.error("account_tool.polymarket.error", extra={"error": str(e)})
        return {"exchange": "polymarket", "error": str(e)}


def get_all_balances() -> dict[str, Any]:
    """Fetch balances from both exchanges. Safe read-only call."""
    kalshi = get_kalshi_balance()
    poly = get_polymarket_account()
    return {
        "kalshi": kalshi,
        "polymarket": poly,
        "timestamp": _now(),
    }


def get_all_positions() -> dict[str, Any]:
    """Fetch all open positions from both exchanges."""
    kalshi_pos = get_kalshi_positions()
    kalshi_orders = get_kalshi_open_orders()
    poly_pos = get_polymarket_positions()
    return {
        "kalshi": {
            "positions": kalshi_pos,
            "open_orders": kalshi_orders,
        },
        "polymarket": {
            "positions": poly_pos,
        },
        "timestamp": _now(),
    }
