"""
tools/chainlink_stream.py
Background WebSocket client for Polymarket's Chainlink-backed real-time price feed.

Stream: wss://ws-live-data.polymarket.com
Topic:  crypto_prices_chainlink  (no auth)
Pairs:  btc/usd, eth/usd, sol/usd, xrp/usd

Architecture: one WebSocket connection per symbol (server doesn't tag symbol in
payload, so we tag by connection). Each worker auto-reconnects on failure.
"""
from __future__ import annotations

import json
import threading
import time
from typing import Any

from logging_config.structured_logger import get_logger

logger = get_logger(__name__)

WS_URL = "wss://ws-live-data.polymarket.com"
TOPIC = "crypto_prices_chainlink"
SYMBOLS = ["btc/usd", "eth/usd", "sol/usd", "xrp/usd"]

SYMBOL_ALIASES = {
    "bitcoin": "btc/usd", "btc": "btc/usd",
    "ethereum": "eth/usd", "eth": "eth/usd",
    "solana": "sol/usd", "sol": "sol/usd",
    "xrp": "xrp/usd", "ripple": "xrp/usd",
}

_lock = threading.RLock()
_latest: dict[str, dict[str, Any]] = {}
_anchors: dict[tuple, float] = {}
_running = False


def _ingest(sym: str, price: float, epoch: float):
    with _lock:
        prev = _latest.get(sym)
        if not prev or epoch >= prev["ts"]:
            _latest[sym] = {"price": price, "ts": epoch}
        minute = int(epoch // 60) * 60
        key = (sym, minute)
        if key not in _anchors:
            _anchors[key] = price
        if len(_anchors) > 4000:
            cutoff = time.time() - 7200
            for k in list(_anchors.keys()):
                if k[1] < cutoff:
                    del _anchors[k]


def _parse_batch(sym: str, msg: str):
    if not msg or msg == "pong":
        return
    try:
        data = json.loads(msg)
    except Exception:
        return
    payload = data.get("payload") if isinstance(data, dict) else None
    records = []
    if isinstance(payload, dict):
        records = payload.get("data") or []
    elif isinstance(data, list):
        records = data
    elif isinstance(data, dict) and ("value" in data or "price" in data):
        records = [data]
    for r in records:
        if not isinstance(r, dict):
            continue
        px = r.get("value") or r.get("price") or r.get("p")
        ts = r.get("timestamp") or r.get("ts")
        if px is None or ts is None:
            continue
        try:
            price = float(px)
            epoch = float(ts) / 1000 if float(ts) > 1e11 else float(ts)
        except (ValueError, TypeError):
            continue
        _ingest(sym, price, epoch)


def _run_symbol_loop(sym: str):
    import websocket
    while _running:
        ws = None
        try:
            ws = websocket.WebSocket()
            ws.settimeout(30)
            ws.connect(WS_URL)
            sub = {"action": "subscribe", "subscriptions": [
                {"topic": TOPIC, "type": "*", "filters": json.dumps({"symbol": sym})}
            ]}
            ws.send(json.dumps(sub))
            logger.info("chainlink_stream.subscribed", extra={"symbol": sym})
            last_ping = time.time()
            while _running:
                try:
                    msg = ws.recv()
                    if msg:
                        _parse_batch(sym, msg)
                    if time.time() - last_ping > 5:
                        try: ws.send("ping")
                        except Exception: pass
                        last_ping = time.time()
                except Exception:
                    break
        except Exception as e:
            logger.warning("chainlink_stream.reconnect",
                           extra={"symbol": sym, "error": str(e)[:120]})
        finally:
            try:
                if ws: ws.close()
            except Exception: pass
        if _running:
            time.sleep(3)


def start() -> bool:
    global _running
    if _running:
        return True
    try:
        import websocket  # noqa
    except ImportError:
        logger.error("chainlink_stream.missing_dep",
                     extra={"hint": "pip install websocket-client"})
        return False
    _running = True
    for sym in SYMBOLS:
        threading.Thread(target=_run_symbol_loop, args=(sym,),
                         daemon=True, name=f"chainlink-{sym}").start()
    return True


def stop():
    global _running
    _running = False


def get_latest(symbol: str) -> dict[str, Any] | None:
    with _lock:
        r = _latest.get(symbol.lower())
    if not r:
        return None
    if time.time() - r["ts"] > 60:
        return None
    return dict(r)


def get_anchor(symbol: str, window_start_epoch: int) -> float | None:
    with _lock:
        minute = int(window_start_epoch // 60) * 60
        return _anchors.get((symbol.lower(), minute))


def resolve_symbol_from_title(title: str) -> str | None:
    t = (title or "").lower()
    for alias, sym in SYMBOL_ALIASES.items():
        if alias in t:
            return sym
    return None


def status() -> dict[str, Any]:
    with _lock:
        return {
            "running": _running,
            "symbols_seen": list(_latest.keys()),
            "latest": dict(_latest),
            "anchors_cached": len(_anchors),
        }
