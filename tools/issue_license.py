"""
tools/issue_license.py
Admin helper — generate a signed license.jwt for a customer.

First run: auto-generates an RSA keypair at config/license_private.pem (NEVER commit)
           and config/license_public.pem (ships with the app).

Usage:
  python -m tools.issue_license --email foo@bar.com --days 30
  python -m tools.issue_license --email foo@bar.com --days 365 --plan pro --out licenses/foo.jwt
  python -m tools.issue_license --lifetime --email foo@bar.com --plan lifetime
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

try:
    import jwt
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
except ImportError:
    print("Install: pip install pyjwt[crypto] cryptography", file=sys.stderr)
    sys.exit(1)

_PRIV = Path("config/license_private.pem")
_PUB = Path("config/license_public.pem")


def ensure_keys():
    if _PRIV.exists() and _PUB.exists():
        return
    print("Generating new RSA-2048 keypair...")
    _PRIV.parent.mkdir(parents=True, exist_ok=True)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    _PRIV.write_bytes(key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ))
    _PUB.write_bytes(key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ))
    print(f"  private: {_PRIV} (KEEP SECRET — gitignored)")
    print(f"  public:  {_PUB}  (commit this so clients can verify)")


def issue(email: str, days: int | None, plan: str, features: list[str], out_path: Path) -> Path:
    ensure_keys()
    priv = _PRIV.read_text()

    claims: dict = {"sub": email, "plan": plan, "iat": int(time.time())}
    if features:
        claims["feat"] = features
    if days is not None:
        claims["exp"] = int(time.time()) + days * 86400

    token = jwt.encode(claims, priv, algorithm="RS256")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(token)
    return out_path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--email", required=True)
    p.add_argument("--days", type=int, default=30)
    p.add_argument("--lifetime", action="store_true", help="No expiry")
    p.add_argument("--plan", default="pro", choices=["free", "pro", "lifetime"])
    p.add_argument("--features", nargs="*", default=[])
    p.add_argument("--out", default="license.jwt")
    a = p.parse_args()

    days = None if a.lifetime else a.days
    out = issue(a.email, days, a.plan, a.features, Path(a.out))
    print(f"License written: {out}")
    print(f"  email: {a.email}  plan: {a.plan}  "
          f"{'lifetime' if a.lifetime else f'{a.days} days'}")


if __name__ == "__main__":
    main()
