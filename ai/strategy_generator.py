"""
ai/strategy_generator.py
Claude-powered strategy proposer.

Runs manually (or scheduled daily) after we have enough outcome data.
Workflow:
  1. Read per-strategy scorecard + recent market patterns.
  2. Identify gaps: market conditions where current strategies don't fire
     but retrospectively would have been profitable.
  3. Prompt Claude (Opus) to generate a new strategy Python module.
  4. Write to strategies/proposed/{name}.py for human review.

NEVER auto-enables. Human must review and move to strategies/core/ manually.
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path

from logging_config.structured_logger import get_logger
from tools.database_tool import _conn

logger = get_logger(__name__)

_PROPOSED_DIR = Path("strategies/proposed")
_MIN_OUTCOMES = int(os.getenv("STRATEGY_GEN_MIN_OUTCOMES", "500"))


def _gather_context() -> dict:
    """Build the context package we give Claude."""
    from core.strategy_scorecard import scorecard, grand_total
    gt = grand_total()
    cards = scorecard()

    with _conn() as con:
        # Markets we had signals on that RESOLVED but we MISSED (no buy)
        missed = con.execute("""
            SELECT s.market_id, s.strategy_name, MAX(s.score), MAX(s.confidence),
                   COUNT(*) n_signals
            FROM signals s
            LEFT JOIN orders o ON o.market_id = s.market_id AND o.status='filled'
            WHERE o.order_id IS NULL
              AND s.timestamp >= datetime('now','-3 day')
            GROUP BY s.market_id
            ORDER BY MAX(s.score) DESC
            LIMIT 20
        """).fetchall()

    return {
        "grand_total": gt,
        "per_strategy": cards,
        "missed_signals_sample": [
            {"market_id": m[0], "strategy": m[1], "max_score": m[2],
             "max_conf": m[3], "n_signals": m[4]}
            for m in missed
        ],
    }


_PROMPT_TEMPLATE = """\
You are proposing a NEW trading strategy for UPAS, a prediction-market alpha system on Polymarket + Kalshi.

CURRENT PERFORMANCE:
{perf_summary}

PER-STRATEGY BREAKDOWN (realized outcomes):
{strategies_md}

CONSTRAINTS:
- Binary markets only (YES/NO outcome).
- Output must be a Python module importable at strategies/proposed/<name>.py.
- Must define `class <Name>(BaseStrategy)` with a `detect(self, markets) -> list[Signal]` method.
- Must NOT target markets expiring in <2 hours (those are banned — too close to gambling).
- Must use reverse-thinking: include at least one falsifiable check that WOULD invalidate the signal.
- Score output in [70,100], confidence in [0.5,0.95].

OUTPUT FORMAT — STRICT JSON ONLY (no prose, no markdown fencing):
{{
  "strategy_name": "snake_case_name",
  "rationale": "one paragraph — what inefficiency this exploits and why existing strategies miss it",
  "expected_win_rate": 0.55,
  "reverse_check": "explicitly — what pattern would tell us we're wrong",
  "module_code": "<full Python source of strategies/proposed/<name>.py>"
}}
"""


def propose_one() -> dict:
    """Generate one proposal. Never auto-enables."""
    ctx = _gather_context()
    gt = ctx["grand_total"]

    if gt["trades"] < _MIN_OUTCOMES:
        return {"ok": False,
                "reason": f"need {_MIN_OUTCOMES} outcomes, have {gt['trades']}"}

    strategies_md = "\n".join(
        f"- {c['strategy']}: n={c['n']} win_rate={c['win_rate']*100:.0f}% "
        f"avg_pnl=${c['avg_pnl_usd']:+.2f} total=${c['total_pnl_usd']:+.2f}"
        for c in ctx["per_strategy"]
    )
    perf_summary = (
        f"trades={gt['trades']} wins={gt['wins']} losses={gt['losses']} "
        f"win_rate={gt['win_rate']*100:.1f}% total_pnl=${gt['total_pnl_usd']:+.2f}"
    )

    prompt = _PROMPT_TEMPLATE.format(
        perf_summary=perf_summary, strategies_md=strategies_md,
    )

    try:
        from ai.scorer import _call_claude
        raw = _call_claude(prompt, tier="A")  # Opus for hard code gen
    except Exception as e:
        return {"ok": False, "reason": f"ai_call_failed: {e}"}

    import json
    m = re.search(r"\{.*\}", raw or "", re.DOTALL)
    if not m:
        return {"ok": False, "reason": "no json in response", "raw": (raw or "")[:200]}
    try:
        payload = json.loads(m.group(0))
    except Exception as e:
        return {"ok": False, "reason": f"json_parse: {e}", "raw": m.group(0)[:200]}

    name = re.sub(r"[^a-z0-9_]", "", payload.get("strategy_name", "").lower()) or "unnamed"
    code = payload.get("module_code", "")
    if not code or "class " not in code or "def detect" not in code:
        return {"ok": False, "reason": "proposal missing class/detect", "name": name}

    _PROPOSED_DIR.mkdir(parents=True, exist_ok=True)
    out = _PROPOSED_DIR / f"{name}.py"
    header = (
        f'"""\nPROPOSED by strategy_generator on {datetime.now(timezone.utc).isoformat()}.\n'
        f"Rationale: {payload.get('rationale','')}\n"
        f"Expected win rate: {payload.get('expected_win_rate')}\n"
        f"Reverse check: {payload.get('reverse_check')}\n"
        f'NOT auto-enabled. Human review required before moving to strategies/core/.\n"""\n'
    )
    out.write_text(header + code, encoding="utf-8")
    logger.info("strategy_generator.proposed",
                extra={"name": name, "path": str(out)})
    return {"ok": True, "name": name, "path": str(out),
            "expected_win_rate": payload.get("expected_win_rate"),
            "rationale": payload.get("rationale", "")[:200]}


if __name__ == "__main__":
    import json
    print(json.dumps(propose_one(), indent=2))
