"""
tools/fees.py
Exchange-specific fee calculators.

Kalshi fee formula (official):
  fee = ceil(0.07 * C * P * (1 - P)) rounded UP to the nearest cent
  where C = contracts, P = price (0..1).
  Reference: https://kalshi.com/docs/fees

Polymarket: no maker/taker fee on standard CLOB markets (2026).
  Kept configurable via POLY_TAKER_FEE_BPS env var in case that changes.
"""
from __future__ import annotations

import math
import os


def kalshi_fee(contracts: int, price: float) -> float:
    """Kalshi per-order fee in USD."""
    if contracts <= 0 or not (0 < price < 1):
        return 0.0
    raw_cents = 7.0 * contracts * price * (1.0 - price)  # 7¢ basis
    return math.ceil(raw_cents) / 100.0


def polymarket_fee(size_usd: float, price: float) -> float:
    bps = float(os.getenv("POLY_TAKER_FEE_BPS", "0"))
    return size_usd * bps / 10_000.0


def order_fee(exchange: str, size_usd: float, price: float) -> float:
    """Single-side fee estimate."""
    if exchange == "kalshi":
        contracts = max(1, round(size_usd / max(price, 0.01)))
        return kalshi_fee(contracts, price)
    if exchange == "polymarket":
        return polymarket_fee(size_usd, price)
    return 0.0


def round_trip_fee(exchange: str, size_usd: float, entry_price: float,
                   exit_price: float | None = None) -> float:
    """Round-trip fee (open + close). Assumes exit at same price if not given."""
    exit_p = exit_price if exit_price is not None else entry_price
    return order_fee(exchange, size_usd, entry_price) + order_fee(exchange, size_usd, exit_p)


def min_edge_required(exchange: str, size_usd: float, price: float) -> float:
    """Minimum price edge (in probability units) needed to break even after round-trip fees."""
    rt = round_trip_fee(exchange, size_usd, price)
    if size_usd <= 0:
        return 0.0
    return rt / size_usd
