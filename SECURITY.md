# Security Policy

## Threat Model

UPAS is a **local-only** trading agent. It runs on your Windows machine, reads your API keys from a local `.env` file, and signs orders client-side. **No secrets are transmitted to any third-party service** (other than the exchanges you are trading on and, optionally, Anthropic's Claude API).

## Secret Handling

| Secret | Location | Transmitted to |
|---|---|---|
| `POLY_PRIVATE_KEY` | `.env` (gitignored) | Never transmitted — used locally to sign orders |
| `POLY_API_KEY` / `POLY_SECRET` | `.env` | Polymarket CLOB API only (HTTPS) |
| `KALSHI_API_KEY_ID` + `.pem` | `.env` + `config/kalshi_private_key.pem` (gitignored) | Kalshi API only (RSA-signed requests) |
| `ANTHROPIC_API_KEY` | `.env` | Anthropic API only (HTTPS), when `CLAUDE_AUTH_MODE=api` |

## What Is Protected

- **`.gitignore`** blocks `.env`, all `*.pem`, all `*.key`, `data/`, `logs/`, `.claude/`, `memory/`, DB sidecars (`*.db-wal`, `*.db-shm`), and credential files
- **All secrets loaded via `os.getenv()`** — there are no hardcoded keys or addresses in source
- **CI secret scanning** (Gitleaks) runs on every push and every PR to catch accidental leaks
- **`.env.example`** contains only placeholder values (`YOUR_POLY_API_KEY`, etc.)

## What Is NOT Protected (by design)

- Your local `.env` file — anyone with access to your machine can read it
- Your local SQLite DB (`data/upas.db`) — contains full trading history, unencrypted
- Your local logs (`logs/*.jsonl`) — may contain order IDs and market addresses

**Recommendation**: full-disk encryption (BitLocker) on the machine running UPAS.

## Reporting a Vulnerability

If you find a security issue:
1. **Do not open a public GitHub issue**
2. Email: tuvalsmail@gmail.com with subject `UPAS SECURITY`
3. Include: affected version, reproduction steps, impact

## Key Rotation

If you suspect a key leak:
1. Stop UPAS (`Ctrl+C` in master window)
2. Revoke the compromised key at the exchange (Polymarket dashboard / Kalshi settings / Anthropic console)
3. Generate a new key, update `.env`
4. Restart UPAS

## Trading Safety

UPAS will place **live orders with real money**. Safety controls:
- `MAX_SINGLE_TRADE_USD` — per-order cap (default $25)
- `MAX_TRADE_EQUITY_PCT` — max 8% of equity per trade
- `MAX_TOTAL_EXPOSURE_USD` — aggregate open-position cap
- `KELLY_FRACTION=0.25` — quarter-Kelly sizing (conservative)
- Exchange floors: $5 Polymarket, $1 Kalshi

To run without placing real orders, use `START_DRY.bat` (dry-run mode).
