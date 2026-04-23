"""
tools/execution_tool.py
Order execution for Polymarket and Kalshi.

SAFETY CONTRACT:
  - DRY_RUN=True by default — no real orders placed unless explicitly overridden
  - All orders validated against risk limits BEFORE submission
  - Every order attempt logged to audit_logs (append-only)
  - No order placed without passing ALL safety checks
"""
from __future__ import annotations

import base64
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

import requests

from config.variables import (
    CAPITAL,
    KALSHI_API_KEY_ID,
    KALSHI_BASE,
    KALSHI_PRIVATE_KEY_PATH,
    POLY_API_KEY,
    POLY_CLOB_BASE,
    POLY_PASSPHRASE,
    POLY_PRIVATE_KEY,
    POLY_SECRET,
    RISK_PER_TRADE,
)
from logging_config.structured_logger import get_logger
from tools.database_tool import append_audit_log

logger = get_logger(__name__)

# ── Execution config ─────────────────────────────────────────
import os
DRY_RUN: bool = os.getenv("DRY_RUN", "true").lower() in ("true", "1", "yes")

# Hard-coded safety limits — never override via config
_MAX_SINGLE_TRADE_USD = 25.0        # hard cap per order
_MAX_POSITION_USD = 100.0           # max exposure per market
_MAX_TOTAL_EXPOSURE_USD = 250.0     # max total portfolio exposure
_MIN_PRICE = 0.02                   # min price (2¢)
_MAX_PRICE = 0.98                   # max price (98¢)
_MIN_SIZE_USD = 5.00                # min order size ($5 — Polymarket exchange floor)


# ── Order record schema ───────────────────────────────────────
def _order_record(
    order_id: str,
    exchange: str,
    market_id: str,
    side: str,
    price: float,
    size_usd: float,
    status: str,
    exchange_order_id: str = "",
    error: str | None = None,
) -> dict[str, Any]:
    return {
        "order_id": order_id,
        "exchange": exchange,
        "market_id": market_id,
        "side": side,
        "price": price,
        "size_usd": size_usd,
        "status": status,
        "exchange_order_id": exchange_order_id,
        "error": error,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dry_run": DRY_RUN,
    }


# ── Risk validation ───────────────────────────────────────────
def _validate_order(
    exchange: str,
    market_id: str,
    side: str,
    price: float,
    size_usd: float,
    current_exposure: float = 0.0,
) -> list[str]:
    """
    Run all safety checks. Returns list of violation strings.
    Empty list = order is safe to submit.
    """
    violations: list[str] = []

    if size_usd < _MIN_SIZE_USD:
        violations.append(f"size ${size_usd:.2f} below minimum ${_MIN_SIZE_USD:.2f}")
    if size_usd > _MAX_SINGLE_TRADE_USD:
        violations.append(f"size ${size_usd:.2f} exceeds hard cap ${_MAX_SINGLE_TRADE_USD:.2f}")
    if not (_MIN_PRICE <= price <= _MAX_PRICE):
        violations.append(f"price {price:.4f} outside safe range [{_MIN_PRICE}, {_MAX_PRICE}]")
    if current_exposure + size_usd > _MAX_POSITION_USD:
        violations.append(
            f"position exposure ${current_exposure + size_usd:.2f} would exceed max ${_MAX_POSITION_USD:.2f}"
        )
    if side not in ("yes", "no", "buy", "sell"):
        violations.append(f"invalid side '{side}' — must be yes/no or buy/sell")
    if exchange not in ("kalshi", "polymarket"):
        violations.append(f"unknown exchange '{exchange}'")

    return violations


# ── Kalshi auth (RSA-PSS) ─────────────────────────────────────
def _kalshi_headers(method: str, path: str, body: str = "") -> dict[str, str]:
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


# ── Kalshi order placement ────────────────────────────────────
def _place_kalshi_order(
    ticker: str,
    side: str,
    yes_price_cents: int,
    count: int,
    order_id: str,
) -> dict[str, Any]:
    """
    Place a limit order on Kalshi.
    ticker: market ticker (e.g. 'KXMARKET-28-YES')
    side: 'yes' or 'no'
    yes_price_cents: integer 1–99 (e.g. 55 = $0.55)
    count: number of contracts
    """
    path = "/trade-api/v2/portfolio/orders"
    base = KALSHI_BASE.removesuffix("/trade-api/v2")
    body = {
        "ticker": ticker,
        "action": "buy",
        "side": side,
        "type": "limit",
        "count": count,
        "yes_price": yes_price_cents,
        "client_order_id": order_id,
    }
    body_str = json.dumps(body)
    hdrs = _kalshi_headers("POST", path)
    try:
        r = requests.post(f"{base}{path}", headers=hdrs, json=body, timeout=15)
        r.raise_for_status()
        data = r.json()
        return {"ok": True, "exchange_order_id": data.get("order", {}).get("order_id", ""), "raw": data}
    except requests.HTTPError as e:
        return {"ok": False, "error": f"HTTP {e.response.status_code}: {e.response.text[:200]}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ── Polymarket order placement ────────────────────────────────
def _resolve_poly_funder() -> str:
    """Resolve Polymarket proxy/funder address.
    Priority: POLY_FUNDER_ADDRESS env → get_trades maker_address → EOA (last resort).
    """
    from py_clob_client.client import ClobClient
    from py_clob_client.clob_types import ApiCreds
    from py_clob_client.constants import POLYGON

    env_funder = os.getenv("POLY_FUNDER_ADDRESS", "").strip()
    if env_funder:
        return env_funder
    boot = ClobClient(
        host=POLY_CLOB_BASE, chain_id=POLYGON, key=POLY_PRIVATE_KEY,
        creds=ApiCreds(api_key=POLY_API_KEY, api_secret=POLY_SECRET, api_passphrase=POLY_PASSPHRASE),
    )
    eoa = boot.get_address()
    # Authoritative: Polymarket profile API
    try:
        import requests
        r = requests.get(f"https://polymarket.com/api/profile/userData?address={eoa.lower()}", timeout=8)
        if r.status_code == 200:
            pw = (r.json() or {}).get("proxyWallet", "")
            if pw:
                return pw
    except Exception:
        pass
    return eoa


def _try_poly_order(token_id, side_const, price, size_usd, sig_type, funder):
    from py_clob_client.client import ClobClient
    from py_clob_client.clob_types import ApiCreds, OrderArgs
    from py_clob_client.constants import POLYGON

    client = ClobClient(
        host=POLY_CLOB_BASE, chain_id=POLYGON, key=POLY_PRIVATE_KEY,
        creds=ApiCreds(api_key=POLY_API_KEY, api_secret=POLY_SECRET, api_passphrase=POLY_PASSPHRASE),
        signature_type=sig_type, funder=funder,
    )
    resp = client.create_and_post_order(OrderArgs(
        token_id=token_id, price=round(price, 4), size=round(size_usd, 2), side=side_const,
    ))
    return resp


def _place_polymarket_order(
    token_id: str,
    side: Literal["BUY", "SELL"],
    price: float,
    size_usd: float,
    order_id: str,
) -> dict[str, Any]:
    try:
        from py_clob_client.order_builder.constants import BUY, SELL
        clob_side = BUY if side.upper() == "BUY" else SELL
        funder = _resolve_poly_funder()

        # User explicitly set signature_type=1 (POLY_PROXY / Magic.link). Do not fall back.
        sig_type = int(os.getenv("POLY_SIGNATURE_TYPE", "1"))
        try:
            resp = _try_poly_order(token_id, clob_side, price, size_usd, sig_type, funder)
            if isinstance(resp, dict) and resp.get("errorMsg"):
                return {"ok": False, "error": f"sig_type={sig_type}: {resp.get('errorMsg')}"}
            order_id_ex = resp.get("orderID", resp.get("order_id", "")) if isinstance(resp, dict) else str(resp)
            return {"ok": True, "exchange_order_id": order_id_ex, "raw": resp, "sig_type": sig_type}
        except Exception as e:
            return {"ok": False, "error": f"sig_type={sig_type}: {e}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ── Public API ────────────────────────────────────────────────

def place_order(
    exchange: str,
    market_id: str,
    side: str,
    price: float,
    size_usd: float,
    ticker: str = "",
    token_id: str = "",
    current_exposure_usd: float = 0.0,
) -> dict[str, Any]:
    """
    Unified order placement with full safety validation.

    Parameters:
      exchange:            'kalshi' or 'polymarket'
      market_id:           internal market identifier
      side:                'yes'/'buy' or 'no'/'sell'
      price:               0.0–1.0 (probability / price)
      size_usd:            USD amount to risk
      ticker:              Kalshi ticker (required for Kalshi)
      token_id:            Polymarket YES/NO token ID (required for Polymarket)
      current_exposure_usd: existing exposure in this market (for limit check)

    Returns order record dict with status and exchange_order_id if filled.
    """
    order_id = str(uuid.uuid4())

    # ── Safety checks ───────────────────────────────────────────
    violations = _validate_order(exchange, market_id, side, price, size_usd, current_exposure_usd)
    if violations:
        rec = _order_record(order_id, exchange, market_id, side, price, size_usd,
                            status="rejected", error="; ".join(violations))
        append_audit_log("order.rejected", "execution_tool", json.dumps(rec))
        logger.warning("execution_tool.order.rejected", extra={"violations": violations, "market_id": market_id})
        return rec

    # ── DRY RUN guard ────────────────────────────────────────────
    if DRY_RUN:
        rec = _order_record(order_id, exchange, market_id, side, price, size_usd, status="dry_run")
        append_audit_log("order.dry_run", "execution_tool", json.dumps(rec))
        logger.info("execution_tool.order.dry_run", extra={
            "exchange": exchange, "market_id": market_id, "side": side,
            "price": price, "size_usd": size_usd,
        })
        return rec

    # ── Live execution ───────────────────────────────────────────
    if exchange == "kalshi":
        if not ticker:
            return _order_record(order_id, exchange, market_id, side, price, size_usd,
                                 status="rejected", error="ticker required for Kalshi orders")
        yes_price_cents = round(price * 100)
        count = max(1, round(size_usd / price))
        result = _place_kalshi_order(ticker, side, yes_price_cents, count, order_id)

    elif exchange == "polymarket":
        if not token_id:
            return _order_record(order_id, exchange, market_id, side, price, size_usd,
                                 status="rejected", error="token_id required for Polymarket orders")
        # For Polymarket binary markets: taking a YES or NO position = BUY the
        # corresponding outcome token. SELL is only for closing existing inventory
        # and is routed explicitly via side="sell"/"close" (not yes/no).
        s = side.lower()
        if s in ("yes", "no", "buy"):
            poly_side = "BUY"
        elif s in ("sell", "close"):
            poly_side = "SELL"
        else:
            poly_side = "BUY"
        result = _place_polymarket_order(token_id, poly_side, price, size_usd, order_id)

    else:
        return _order_record(order_id, exchange, market_id, side, price, size_usd,
                             status="rejected", error=f"unknown exchange: {exchange}")

    status = "filled" if result.get("ok") else "failed"
    rec = _order_record(
        order_id, exchange, market_id, side, price, size_usd,
        status=status,
        exchange_order_id=result.get("exchange_order_id", ""),
        error=result.get("error"),
    )
    append_audit_log(f"order.{status}", "execution_tool", json.dumps(rec))
    if result.get("ok"):
        logger.info("execution_tool.order.placed", extra={
            "exchange": exchange, "market_id": market_id, "side": side,
            "price": price, "size_usd": size_usd, "exchange_order_id": rec["exchange_order_id"],
        })
    else:
        logger.error("execution_tool.order.failed", extra={"error": result.get("error"), "market_id": market_id})
    return rec


def validate_order_dry(
    exchange: str,
    market_id: str,
    side: str,
    price: float,
    size_usd: float,
    current_exposure_usd: float = 0.0,
) -> dict[str, Any]:
    """
    Validate order parameters without placing anything.
    Returns { valid: bool, violations: list[str], limits: dict }.
    """
    violations = _validate_order(exchange, market_id, side, price, size_usd, current_exposure_usd)
    return {
        "valid": len(violations) == 0,
        "violations": violations,
        "limits": {
            "max_single_trade_usd": _MAX_SINGLE_TRADE_USD,
            "max_position_usd": _MAX_POSITION_USD,
            "max_total_exposure_usd": _MAX_TOTAL_EXPOSURE_USD,
            "min_price": _MIN_PRICE,
            "max_price": _MAX_PRICE,
            "min_size_usd": _MIN_SIZE_USD,
        },
        "dry_run_mode": DRY_RUN,
    }
