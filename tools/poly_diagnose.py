"""
tools/poly_diagnose.py
Diagnose Polymarket funding issues. Prints:
  - EOA (derived from private key)
  - Proxy wallet per Polymarket profile API
  - Configured POLY_FUNDER_ADDRESS env
  - USDC.e balance on Polygon for EOA + proxy
  - USDC allowance to the Polymarket CTF Exchange
Run: python -m tools.poly_diagnose
"""
from __future__ import annotations

import os
import json
import requests

from config.variables import (
    POLY_CLOB_BASE, POLY_PRIVATE_KEY, POLY_API_KEY, POLY_SECRET, POLY_PASSPHRASE,
)

POLYGON_RPCS = [
    os.getenv("POLYGON_RPC", "").strip() or None,
    "https://polygon.llamarpc.com",
    "https://polygon.drpc.org",
    "https://rpc.ankr.com/polygon",
    "https://polygon-bor-rpc.publicnode.com",
    "https://1rpc.io/matic",
]
POLYGON_RPCS = [u for u in POLYGON_RPCS if u]
USDC_NATIVE = "0x3c499c542cef5e3811e1192ce70d8cc03d5c3359"   # USDC (native) on Polygon
USDC_BRIDGED = "0x2791bca1f2de4661ed88a30c99a7a9449aa84174"  # USDC.e (bridged)
CTF_EXCHANGE = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"
NEG_RISK_EXCHANGE = "0xC5d563A36AE78145C45a50134d48A1215220f80a"


def _rpc(method: str, params: list):
    last_err = None
    for url in POLYGON_RPCS:
        try:
            r = requests.post(url, json={
                "jsonrpc": "2.0", "id": 1, "method": method, "params": params,
            }, timeout=10)
            if r.status_code != 200:
                last_err = f"{url}: HTTP {r.status_code}"
                continue
            j = r.json()
            if "error" in j:
                last_err = f"{url}: {j['error']}"
                continue
            return j.get("result")
        except Exception as e:
            last_err = f"{url}: {e}"
    raise RuntimeError(last_err or "all RPCs failed")


def _balance_of(token: str, holder: str) -> int:
    # balanceOf(address) selector 0x70a08231
    data = "0x70a08231" + holder[2:].rjust(64, "0").lower()
    out = _rpc("eth_call", [{"to": token, "data": data}, "latest"])
    return int(out, 16) if out else 0


def _allowance(token: str, owner: str, spender: str) -> int:
    # allowance(address,address) selector 0xdd62ed3e
    data = "0xdd62ed3e" + owner[2:].rjust(64, "0").lower() + spender[2:].rjust(64, "0").lower()
    out = _rpc("eth_call", [{"to": token, "data": data}, "latest"])
    return int(out, 16) if out else 0


def main():
    from py_clob_client.client import ClobClient
    from py_clob_client.clob_types import ApiCreds
    from py_clob_client.constants import POLYGON

    client = ClobClient(
        host=POLY_CLOB_BASE, chain_id=POLYGON, key=POLY_PRIVATE_KEY,
        creds=ApiCreds(api_key=POLY_API_KEY, api_secret=POLY_SECRET, api_passphrase=POLY_PASSPHRASE),
    )
    eoa = client.get_address()
    env_funder = os.getenv("POLY_FUNDER_ADDRESS", "").strip()

    # Profile API proxy
    proxy = None
    try:
        r = requests.get(f"https://polymarket.com/api/profile/userData?address={eoa.lower()}", timeout=8)
        if r.status_code == 200:
            proxy = (r.json() or {}).get("proxyWallet")
    except Exception as e:
        proxy = f"(profile lookup failed: {e})"

    print("=" * 70)
    print(f"EOA (signer):           {eoa}")
    print(f"Proxy (profile API):    {proxy}")
    print(f"POLY_FUNDER_ADDRESS:    {env_funder or '(not set)'}")
    print("=" * 70)

    addrs = {"EOA": eoa}
    if isinstance(proxy, str) and proxy.startswith("0x"):
        addrs["Proxy"] = proxy
    if env_funder and env_funder.lower() not in (eoa.lower(), (proxy or "").lower()):
        addrs["EnvFunder"] = env_funder

    print(f"\n{'Address':<12} {'USDC native':>16} {'USDC.e':>16} {'Allow->CTF':>16} {'Allow->NegRisk':>16}")
    print("-" * 78)
    for label, addr in addrs.items():
        try:
            n = _balance_of(USDC_NATIVE, addr) / 1e6
            b = _balance_of(USDC_BRIDGED, addr) / 1e6
            a1 = _allowance(USDC_NATIVE, addr, CTF_EXCHANGE) / 1e6
            a1b = _allowance(USDC_BRIDGED, addr, CTF_EXCHANGE) / 1e6
            a2 = _allowance(USDC_NATIVE, addr, NEG_RISK_EXCHANGE) / 1e6
            a2b = _allowance(USDC_BRIDGED, addr, NEG_RISK_EXCHANGE) / 1e6
            print(f"{label:<12} n={n:>12,.2f} b={b:>12,.2f}  "
                  f"CTF: n={a1:,.0f}/b={a1b:,.0f}   NR: n={a2:,.0f}/b={a2b:,.0f}")
        except Exception as e:
            print(f"{label:<12} ERR: {e}")

    print("\nInterpretation:")
    print("- Polymarket holds user funds in the PROXY wallet (sig_type=1).")
    print("- For orders to succeed: USDC balance > 0 AND allowance -> exchange > 0.")
    print("- If EOA has USDC but Proxy does not: funds are on the wrong address.")
    print("- If balance exists but allowance is 0: approve via Polymarket UI")
    print("  (Portfolio -> 'Enable trading' or deposit flow re-approves).")


if __name__ == "__main__":
    main()
