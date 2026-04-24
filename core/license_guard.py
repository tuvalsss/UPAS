"""
core/license_guard.py
Offline JWT license verification.

License file: license.jwt (path via LICENSE_PATH env, default ./license.jwt)
Public key:   config/license_public.pem (shipped with the app)

JWT claims:
  sub:  user email
  exp:  expiry unix ts
  feat: list of enabled feature flags (optional)
  plan: "free"|"pro"|"lifetime" (optional)

Behavior:
  - If LICENSE_REQUIRED=0 (default for dev/open-source): warn only, never block.
  - If LICENSE_REQUIRED=1: fail hard on missing/invalid/expired.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_PUB_PATH = Path(os.getenv("LICENSE_PUBLIC_KEY", "config/license_public.pem"))
_LIC_PATH = Path(os.getenv("LICENSE_PATH", "license.jwt"))
_REQUIRED = os.getenv("LICENSE_REQUIRED", "0") == "1"


def verify() -> dict:
    """
    Returns {ok, email, plan, expiry, features, reason}.
    Never raises — caller inspects `ok`.
    """
    if not _REQUIRED and not _LIC_PATH.exists():
        return {"ok": True, "email": "open-source", "plan": "free",
                "expiry": None, "features": [], "reason": "license-not-required"}

    if not _LIC_PATH.exists():
        return _fail("license file not found — place license.jwt in project root")
    if not _PUB_PATH.exists():
        return _fail(f"public key missing at {_PUB_PATH}")

    try:
        import jwt  # PyJWT
    except ImportError:
        return _fail("PyJWT not installed — run: pip install pyjwt[crypto]")

    try:
        token = _LIC_PATH.read_text().strip()
        pub = _PUB_PATH.read_text()
        claims = jwt.decode(token, pub, algorithms=["RS256"])
    except Exception as e:
        return _fail(f"invalid license signature: {e}")

    exp = claims.get("exp")
    if exp and datetime.fromtimestamp(exp, timezone.utc) < datetime.now(timezone.utc):
        return _fail(f"license expired on {datetime.fromtimestamp(exp, timezone.utc).date()}")

    # Revocation check — the admin can publish config/revoked_jti.txt and any
    # license whose jti appears there stops validating.
    jti = claims.get("jti", "")
    revoked_path = Path(os.getenv("LICENSE_REVOKED_PATH", "config/revoked_jti.txt"))
    if jti and revoked_path.exists():
        try:
            revoked = {line.strip() for line in revoked_path.read_text().splitlines() if line.strip()}
            if jti in revoked:
                return _fail(f"license revoked (jti={jti[:8]}...)")
        except Exception:
            pass

    return {
        "ok": True,
        "email": claims.get("sub", "unknown"),
        "plan": claims.get("plan", "pro"),
        "expiry": datetime.fromtimestamp(exp, timezone.utc).isoformat() if exp else None,
        "features": claims.get("feat", []),
        "is_admin": claims.get("plan") == "admin" or "*" in (claims.get("feat") or []),
        "jti": jti,
        "reason": "valid",
    }


def _fail(reason: str) -> dict:
    return {"ok": False, "email": None, "plan": None,
            "expiry": None, "features": [], "reason": reason}


def guard_or_exit():
    """Call at startup. Exits the process if LICENSE_REQUIRED=1 and license invalid."""
    res = verify()
    if res["ok"]:
        if res["reason"] == "license-not-required":
            return res
        days_left = ""
        if res.get("expiry"):
            dt = datetime.fromisoformat(res["expiry"])
            d = (dt - datetime.now(timezone.utc)).days
            days_left = f" ({d} days left)"
        print(f"[license] OK — {res['email']} plan={res['plan']}{days_left}")
        return res

    msg = f"[license] FAILED: {res['reason']}"
    if _REQUIRED:
        print(msg, file=sys.stderr)
        print("Obtain a license at: https://github.com/tuvalsss/UPAS", file=sys.stderr)
        sys.exit(2)
    print(f"[license] WARN: {res['reason']} (LICENSE_REQUIRED=0, continuing)")
    return res


if __name__ == "__main__":
    import json
    print(json.dumps(verify(), indent=2))
