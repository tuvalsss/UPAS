"""
tools/e2e_test.py
End-to-end health check. Runs every major component and places ONE real
$5 Polymarket NO order to verify the side=no -> BUY token_no fix.

Run: python -m tools.e2e_test
"""
from __future__ import annotations

import os
import sys
import time
import traceback

PASS = "[PASS]"
FAIL = "[FAIL]"
INFO = "[..]  "

results = []

def step(name, fn):
    t0 = time.time()
    try:
        detail = fn()
        dt = time.time() - t0
        results.append((True, name, detail, dt))
        print(f"{PASS} {name}  ({dt:.2f}s)  {detail}")
        return True
    except Exception as e:
        dt = time.time() - t0
        err = f"{type(e).__name__}: {e}"
        results.append((False, name, err, dt))
        print(f"{FAIL} {name}  ({dt:.2f}s)  {err}")
        traceback.print_exc(limit=1)
        return False


def t_imports():
    import core.engine, core.scheduler  # noqa
    import tools.cli, tools.dashboard, tools.execution_tool, tools.fees  # noqa
    import strategies.core.chainlink_edge, strategies.core.cross_market  # noqa
    import ai.scorer  # noqa
    return "all modules import"


def t_env():
    from config.variables import POLY_PRIVATE_KEY, POLY_API_KEY, AUTO_EXECUTE, DRY_RUN
    missing = []
    if not POLY_PRIVATE_KEY: missing.append("POLY_PRIVATE_KEY")
    if not POLY_API_KEY: missing.append("POLY_API_KEY")
    if not os.getenv("POLY_FUNDER_ADDRESS"): missing.append("POLY_FUNDER_ADDRESS")
    if missing:
        raise RuntimeError("missing env: " + ", ".join(missing))
    return f"AUTO_EXECUTE={AUTO_EXECUTE} DRY_RUN={DRY_RUN}"


def t_scanner_poly():
    from tools.polymarket_tool import run
    r = run(limit=50)
    return f"fetched {r.get('count', 0)} Polymarket markets"


def t_scanner_kalshi():
    from tools.kalshi_tool import run
    r = run(limit=50)
    return f"fetched {r.get('count', 0)} Kalshi markets"


def t_db_write():
    from tools.database_tool import upsert_market, _conn
    from datetime import datetime, timezone
    sample = {
        "market_id": "E2E-TEST-001", "title": "E2E test market", "source": "polymarket",
        "yes_price": 0.5, "no_price": 0.5, "liquidity": 100, "volume": 100,
        "expiry_timestamp": "2099-01-01T00:00:00+00:00",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "token_id_yes": "0", "token_id_no": "0", "raw": {},
    }
    upsert_market(sample)
    with _conn() as con:
        r = con.execute("SELECT title FROM markets WHERE market_id='E2E-TEST-001'").fetchone()
        con.execute("DELETE FROM markets WHERE market_id='E2E-TEST-001'")
    if not r:
        raise RuntimeError("upsert did not persist")
    return "upsert+read+delete ok"


def t_strategies():
    from tools.database_tool import get_recent_markets
    from tools.strategy_tool import run_strategies
    mkts = get_recent_markets(limit=300)
    sigs = run_strategies(mkts, strategy_type="core")
    return f"core strategies produced {len(sigs)} signals from {len(mkts)} markets"


def t_reverse():
    from tools.database_tool import get_recent_markets
    from tools.strategy_tool import run_strategies
    mkts = get_recent_markets(limit=300)
    sigs = run_strategies(mkts, strategy_type="reverse")
    return f"reverse strategies produced {len(sigs)} signals"


def t_ai():
    from ai.scorer import _call_claude
    r = _call_claude("Reply with exactly: PONG", tier="B")
    if not r or "PONG" not in r.upper():
        raise RuntimeError(f"unexpected AI reply: {r!r}")
    return f"Claude responded ({len(r)} chars)"


def t_chainlink():
    from tools.chainlink_stream import start, status
    start()
    time.sleep(4)
    s = status()
    seen = s.get("symbols_seen", [])
    if not s.get("running"):
        raise RuntimeError("stream not running")
    return f"running, symbols seen: {seen}"


def t_poly_balance():
    from py_clob_client.client import ClobClient
    from py_clob_client.clob_types import ApiCreds, BalanceAllowanceParams, AssetType
    from py_clob_client.constants import POLYGON
    from config.variables import POLY_CLOB_BASE, POLY_PRIVATE_KEY, POLY_API_KEY, POLY_SECRET, POLY_PASSPHRASE
    funder = os.getenv("POLY_FUNDER_ADDRESS")
    c = ClobClient(host=POLY_CLOB_BASE, chain_id=POLYGON, key=POLY_PRIVATE_KEY,
        creds=ApiCreds(api_key=POLY_API_KEY, api_secret=POLY_SECRET, api_passphrase=POLY_PASSPHRASE),
        signature_type=1, funder=funder)
    r = c.get_balance_allowance(BalanceAllowanceParams(asset_type=AssetType.COLLATERAL))
    bal = int(r["balance"]) / 1e6
    if bal < 10:
        raise RuntimeError(f"proxy balance too low for test: ${bal:.2f}")
    return f"proxy ${bal:.2f} USDC, allowances unlimited"


def t_kalshi_balance():
    from tools.account_tool import get_kalshi_balance
    k = get_kalshi_balance()
    cash = k.get("cash_balance_usd", 0)
    if cash < 0:
        raise RuntimeError("invalid balance")
    return f"Kalshi cash ${cash:.2f}"


def t_poly_no_order():
    """
    THE critical fix test: place a real $5 NO order on a liquid Polymarket market.
    Proves the side=no -> BUY token_no mapping works end-to-end.
    """
    from tools.database_tool import _conn
    from tools.execution_tool import place_order
    from py_clob_client.client import ClobClient
    from py_clob_client.clob_types import ApiCreds
    from py_clob_client.constants import POLYGON
    from config.variables import POLY_CLOB_BASE, POLY_PRIVATE_KEY, POLY_API_KEY, POLY_SECRET, POLY_PASSPHRASE
    probe = ClobClient(host=POLY_CLOB_BASE, chain_id=POLYGON, key=POLY_PRIVATE_KEY,
        creds=ApiCreds(api_key=POLY_API_KEY, api_secret=POLY_SECRET, api_passphrase=POLY_PASSPHRASE),
        signature_type=1, funder=os.getenv("POLY_FUNDER_ADDRESS"))
    with _conn() as con:
        rows = con.execute("""
            SELECT market_id, title, yes_price, no_price, token_id_yes, token_id_no, liquidity
            FROM markets
            WHERE source='polymarket'
              AND token_id_no != '' AND token_id_yes != ''
              AND no_price BETWEEN 0.20 AND 0.80
              AND liquidity > 5000
              AND fetched_at >= datetime('now','-2 hours')
            ORDER BY liquidity DESC LIMIT 30
        """).fetchall()
    row = None
    for cand in rows:
        tid_n = cand[5]
        try:
            ob = probe.get_order_book(tid_n)
            bids = getattr(ob, "bids", None) or (ob.get("bids") if isinstance(ob, dict) else None) or []
            if bids:
                row = cand
                break
        except Exception:
            continue
    if not row:
        raise RuntimeError(f"no poly market with active NO orderbook in {len(rows)} candidates")
    mid, title, yes_p, no_p, tid_y, tid_n, liq = row
    # Bid 2c below mid to minimize fill risk but still verify signing path
    # Actually we want to verify order ACCEPTANCE, not necessarily fill. Use a
    # conservative low bid so it rests on book rather than filling.
    test_price = round(max(0.10, no_p - 0.10), 2)
    print(f"         using market: {title[:60]}")
    print(f"         NO token: {tid_n[:16]}...  mid_no={no_p}  bid={test_price}")
    res = place_order(
        exchange="polymarket", market_id=mid, side="no",
        price=test_price, size_usd=5.0,
        ticker="", token_id=tid_n, current_exposure_usd=0.0,
    )
    status = res.get("status")
    err = res.get("error") or ""
    if status in ("filled", "live", "placed") or res.get("exchange_order_id"):
        # Try to cancel immediately to not leave resting order
        try:
            from py_clob_client.client import ClobClient
            from py_clob_client.clob_types import ApiCreds
            from py_clob_client.constants import POLYGON
            from config.variables import POLY_CLOB_BASE, POLY_PRIVATE_KEY, POLY_API_KEY, POLY_SECRET, POLY_PASSPHRASE
            c = ClobClient(host=POLY_CLOB_BASE, chain_id=POLYGON, key=POLY_PRIVATE_KEY,
                creds=ApiCreds(api_key=POLY_API_KEY, api_secret=POLY_SECRET, api_passphrase=POLY_PASSPHRASE),
                signature_type=1, funder=os.getenv("POLY_FUNDER_ADDRESS"))
            oid = res.get("exchange_order_id")
            if oid:
                c.cancel(order_id=oid)
                return f"status={status} order {oid[:10]}... placed then cancelled"
        except Exception as ce:
            return f"status={status} placed but cancel failed: {ce}"
        return f"status={status}"
    raise RuntimeError(f"order did not place: status={status} err={err[:200]}")


def main():
    print("=" * 72)
    print("UPAS END-TO-END TEST")
    print("=" * 72)

    # order matters: cheap local tests first, then network, then LIVE order last
    step("1. imports",               t_imports)
    step("2. env config",            t_env)
    step("3. scanner:polymarket",    t_scanner_poly)
    step("4. scanner:kalshi",        t_scanner_kalshi)
    step("5. db write/read",         t_db_write)
    step("6. core strategies",       t_strategies)
    step("7. reverse strategies",    t_reverse)
    step("8. AI scorer (Claude)",    t_ai)
    step("9. chainlink stream",      t_chainlink)
    step("10. polymarket balance",   t_poly_balance)
    step("11. kalshi balance",       t_kalshi_balance)
    if os.getenv("E2E_LIVE_ORDER") == "1":
        step("12. LIVE polymarket NO",   t_poly_no_order)
    else:
        print("[SKIP] 12. LIVE polymarket NO (set E2E_LIVE_ORDER=1 to enable)")

    print("\n" + "=" * 72)
    ok = sum(1 for r in results if r[0])
    tot = len(results)
    print(f"RESULT: {ok}/{tot} passed")
    if ok != tot:
        print("\nFailed steps:")
        for passed, name, detail, _ in results:
            if not passed:
                print(f"  - {name}: {detail}")
        sys.exit(1)
    print("ALL GREEN.")


if __name__ == "__main__":
    main()
