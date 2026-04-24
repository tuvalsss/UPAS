"""
core/engine.py
Full UPAS pipeline:
Scan → Normalize → Strategy → Reverse Strategy → Meta Strategy
→ Uncertainty Check → AI Score → Store → Alert → Checkpoint
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any

from config.variables import (
    AUTO_EXECUTE,
    DRY_RUN,
    EXPIRY_HOURS_MAX,
    LIQUIDITY_MIN,
    MIN_CONFIDENCE_EXEC,
    MIN_SIGNAL_SCORE,
    REVERSE_MODE_ENABLED,
    UNCERTAINTY_THRESHOLD,
    YES_PRICE_MAX,
    YES_PRICE_MIN,
)
from core.uncertainty_engine import score as uncertainty_score
from core.question_router import ask as ask_user
from tools.strategy_tool import run_strategies
from reverse_strategies.reverse_validator import validate_all
from ai.scorer import rank_signals
from ai.reasoning import explain
from tools.database_tool import (
    upsert_market,
    insert_signal,
    insert_score,
    insert_order,
    append_audit_log,
    log_uncertainty_event,
    get_market_by_market_id,
    get_recent_orders,
)
from tools.alert_tool import send_alert
from tools.checkpoint_tool import save as save_checkpoint
from logging_config.structured_logger import get_logger

logger = get_logger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _filter_markets(markets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Apply config-based filters to market list."""
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    filtered = []
    for m in markets:
        yes = m.get("yes_price", 0.0)
        liq = m.get("liquidity", 0.0)
        if not (YES_PRICE_MIN <= yes <= YES_PRICE_MAX):
            continue
        if liq < LIQUIDITY_MIN:
            continue
        expiry = m.get("expiry_timestamp", "")
        min_hours = float(os.getenv("EXPIRY_HOURS_MIN", "2"))
        if expiry:
            try:
                exp_dt = datetime.fromisoformat(expiry.replace("Z", "+00:00"))
                hours = (exp_dt - now).total_seconds() / 3600
                if hours > EXPIRY_HOURS_MAX or hours < 0:
                    continue
                # Skip sub-N-hour markets — too short to do anything but gamble.
                # These are the Bitcoin/ETH "Up/Down 15-min window" crypto flips
                # that have no real edge once spread+fees are accounted for.
                if hours < min_hours:
                    continue
            except Exception:
                pass
        filtered.append(m)
    return filtered


def run_pipeline(
    run_id: str | None = None,
    verbose: bool = False,
    strict: bool = False,
    non_interactive: bool = False,
) -> dict[str, Any]:
    """
    Execute one full pipeline pass.

    Returns:
        {
            run_id, markets_scanned, signals_generated,
            ranked_signals, alerts_sent, checkpoint_id, timestamp
        }
    """
    run_id = run_id or str(uuid.uuid4())
    state: dict[str, Any] = {"run_id": run_id, "stage": "init"}

    logger.info("engine.pipeline.start", extra={"run_id": run_id})
    append_audit_log("pipeline_start", "engine", {"run_id": run_id})

    # Ensure Chainlink stream is running (idempotent, background threads)
    try:
        from tools.chainlink_stream import start as _cl_start
        _cl_start()
    except Exception as _e:
        logger.warning("engine.chainlink_stream.init_failed", extra={"error": str(_e)})

    # ── STAGE 1: Scan ────────────────────────────────────────
    state["stage"] = "scan"
    save_checkpoint("scan_start", state, run_id)

    from tools.polymarket_tool import run as poly_run
    from tools.kalshi_tool import run as kalshi_run

    poly_result = poly_run(limit=500)
    kalshi_result = kalshi_run(limit=500, max_pages=20)

    all_markets = poly_result.get("markets", []) + kalshi_result.get("markets", [])
    logger.info("engine.scan.done", extra={"total": len(all_markets)})

    # ── STAGE 2: Normalize + Filter ──────────────────────────
    state["stage"] = "normalize"
    markets = _filter_markets(all_markets)
    logger.info("engine.normalize.done", extra={"filtered": len(markets)})

    # Store markets to DB
    inserted = sum(1 for m in markets if upsert_market(m))
    logger.info("engine.markets.stored", extra={"inserted": inserted})

    if not markets:
        logger.warning("engine.no_markets")
        return {"run_id": run_id, "markets_scanned": 0, "signals_generated": 0,
                "ranked_signals": [], "alerts_sent": 0, "timestamp": _now()}

    save_checkpoint("normalize_done", {**state, "market_count": len(markets)}, run_id)

    # ── STAGE 3: Core + Meta Strategies ─────────────────────
    state["stage"] = "strategy"
    forward_signals = run_strategies(markets, strategy_type="core")
    meta_signals = run_strategies(markets, strategy_type="meta", all_signals=forward_signals)
    all_forward = forward_signals + meta_signals

    logger.info("engine.strategy.done",
                extra={"forward": len(forward_signals), "meta": len(meta_signals)})
    save_checkpoint("strategy_done", {**state, "signal_count": len(all_forward)}, run_id)

    # Store signals
    for sig in all_forward:
        try:
            insert_signal(sig)
        except Exception as e:
            logger.error("engine.signal.store_error", extra={"error": str(e)})

    # ── STAGE 4: Reverse Strategy + Validation ───────────────
    state["stage"] = "reverse"
    reverse_validations: list[dict[str, Any]] = []

    if REVERSE_MODE_ENABLED:
        reverse_signals = run_strategies(markets, strategy_type="reverse")
        for sig in reverse_signals:
            try:
                insert_signal(sig)
            except Exception:
                pass
        reverse_validations = validate_all(all_forward, markets)
        logger.info("engine.reverse.done",
                    extra={"reverse_signals": len(reverse_signals),
                           "validations": len(reverse_validations)})
        save_checkpoint("reverse_done", state, run_id)

    # ── STAGE 5: Uncertainty Check ───────────────────────────
    state["stage"] = "uncertainty"
    for m in markets[:5]:  # Spot-check top markets
        assessment = uncertainty_score(m, all_forward)
        if assessment["uncertainty"] >= UNCERTAINTY_THRESHOLD:
            log_uncertainty_event({**assessment, "stage": "uncertainty_check"})
            if not non_interactive:
                ask_user(
                    stage="uncertainty_check",
                    issue=f"Uncertainty {assessment['uncertainty']:.2f} on market '{m.get('title','')[:50]}'. "
                          f"Gaps: {assessment['gaps']}. Conflicts: {assessment['conflicts']}",
                    market=m,
                    checkpoint_state=state,
                )

    # ── STAGE 6: AI Scoring ──────────────────────────────────
    state["stage"] = "score"
    ranked = rank_signals(all_forward, reverse_validations, meta_signals)

    for scored_sig in ranked:
        try:
            insert_score({
                "score_id": scored_sig.get("score_id", str(uuid.uuid4())),
                "signal_id": scored_sig.get("signal_id", ""),
                "ai_score": scored_sig.get("ai_score", 0),
                "combined_score": scored_sig.get("combined_score", 0),
                "confidence": scored_sig.get("confidence", 0),
                "model_used": scored_sig.get("model_used", "rule_based"),
                "timestamp": _now(),
            })
        except Exception:
            pass

    logger.info("engine.score.done", extra={"ranked": len(ranked)})
    save_checkpoint("score_done", state, run_id)

    # ── STAGE 7: Alert ───────────────────────────────────────
    state["stage"] = "alert"
    alerts_sent = 0
    top_signals = [s for s in ranked if s.get("combined_score", 0) >= 50][:5]

    for sig in top_signals:
        reasoning = explain(sig)
        try:
            send_alert(
                market_title=sig.get("title", sig.get("market_id", ""))[:80],
                source_platform=sig.get("source", ""),
                signal_type=sig.get("direction", "forward"),
                score=sig.get("combined_score", 0),
                confidence=sig.get("confidence", 0),
                uncertainty_score=sig.get("uncertainty", 0),
                reasoning_summary=reasoning.get("summary", "")[:120],
                suggested_action=sig.get("suggested_action", "WATCH"),
                timestamp=_now(),
            )
            alerts_sent += 1
        except Exception as e:
            logger.error("engine.alert.error", extra={"error": str(e)})

    # ── STAGE 8: Execution (if AUTO_EXECUTE enabled) ────────────
    orders_placed = 0
    state["stage"] = "execute"

    if AUTO_EXECUTE:
        from tools.execution_tool import place_order

        # Tier routing: REAL, NEAR-MISS PAPER, or discard.
        #   REAL:       score >= MIN_SIGNAL_SCORE       AND conf >= MIN_CONFIDENCE_EXEC
        #   PAPER:      score in [PAPER_MIN_SCORE, REAL) AND conf >= PAPER_MIN_CONF
        #   (also:     any signal from strategy in _PAPER_STRATEGIES -> PAPER)
        # Paper trades cost nothing but produce resolution data we use to
        # learn whether our REAL thresholds are tuned correctly (via the
        # threshold_tuner). No trades = no feedback.
        _PAPER_MIN_SCORE = float(os.getenv("PAPER_MIN_SCORE", "60"))
        _PAPER_MIN_CONF = float(os.getenv("PAPER_MIN_CONF", "0.50"))
        _PAPER_MAX_PER_CYCLE = int(os.getenv("PAPER_MAX_PER_CYCLE", "5"))
        from tools.strategy_tool import _PAPER_STRATEGIES

        real_candidates = []
        paper_candidates = []
        for s in ranked:
            score = float(s.get("combined_score", 0) or 0)
            conf = float(s.get("confidence", 0) or 0)
            strat = s.get("strategy_name", "")
            forced_paper = strat in _PAPER_STRATEGIES
            if score >= MIN_SIGNAL_SCORE and conf >= MIN_CONFIDENCE_EXEC and not forced_paper:
                real_candidates.append(s)
            elif forced_paper or (score >= _PAPER_MIN_SCORE and conf >= _PAPER_MIN_CONF):
                s["paper_trade"] = True
                # Tag the reason so we can segment in analytics:
                #   "near_miss" (would have been REAL under looser thresholds)
                #   "proposed_strategy" (strategy is explicitly PAPER-only)
                s["paper_reason"] = "proposed_strategy" if forced_paper else "near_miss"
                paper_candidates.append(s)

        candidates = real_candidates + paper_candidates

        # Dedup: skip markets with LIVE filled/pending order in last 2h (short cooldown).
        # 24h was too long — same market kept getting blocked after one trade.
        recent_market_ids = {
            o["market_id"] for o in get_recent_orders(hours=2)
            if not o.get("dry_run") and o.get("status") in ("filled", "pending", "submitted")
        }

        # Post-Kelly sizing: allow up to 3 orders per cycle (sizes are capped individually)
        max_orders_per_cycle = int(os.getenv("MAX_ORDERS_PER_CYCLE", "3"))
        paper_placed = 0

        for sig in candidates:
            is_paper = bool(sig.get("paper_trade"))
            # Paper trades don't count against real-order cycle cap
            if not is_paper and orders_placed >= max_orders_per_cycle:
                continue
            if is_paper and paper_placed >= _PAPER_MAX_PER_CYCLE:
                continue
            mid = sig.get("market_id", "")
            if mid in recent_market_ids:
                logger.info("engine.execute.skip_duplicate", extra={"market_id": mid})
                continue

            # Parse side from suggested_action ("BUY YES" / "BUY NO" / "WATCH")
            action = sig.get("suggested_action", "WATCH").upper()
            if "YES" in action:
                side = "yes"
            elif "NO" in action:
                side = "no"
            else:
                continue  # WATCH — no trade

            # Authoritative market metadata from DB (signals don't carry price/liq)
            db_market = get_market_by_market_id(mid)
            if not db_market:
                logger.warning("engine.execute.skip_no_market_row", extra={"market_id": mid})
                continue

            source = db_market.get("source", "")
            yes_price = float(db_market.get("yes_price", 0) or 0)
            no_price = float(db_market.get("no_price", 0) or 0)
            liquidity = float(db_market.get("liquidity", 0) or 0)
            title = db_market.get("title", "")

            price = yes_price if side == "yes" else no_price

            # Safety gates — refuse to trade on bad/missing metadata
            if not (0.02 <= price <= 0.98):
                logger.warning("engine.execute.skip_bad_price",
                               extra={"market_id": mid, "price": price, "side": side})
                continue
            if liquidity < LIQUIDITY_MIN:
                logger.warning("engine.execute.skip_low_liq",
                               extra={"market_id": mid, "liquidity": liquidity})
                continue

            ticker = mid if source == "kalshi" else ""
            token_id = (
                db_market.get("token_id_yes", "") if side == "yes"
                else db_market.get("token_id_no", "")
            ) if source == "polymarket" else ""

            if source == "polymarket" and not token_id:
                logger.warning("engine.execute.skip_no_token", extra={"market_id": mid, "side": side})
                continue
            if source == "kalshi" and not ticker:
                logger.warning("engine.execute.skip_no_ticker", extra={"market_id": mid})
                continue

            # ── Kelly-fraction sizing ──
            from tools.sizing import kelly_size_usd
            from tools.fees import round_trip_fee
            score = float(sig.get("combined_score", 0))
            ai_conf = float(sig.get("confidence", sig.get("ai_confidence", 0.5)) or 0.5)

            # Exchange-specific equity snapshot (best-effort; fall back to conservative)
            try:
                if source == "polymarket":
                    from tools.account_tool import get_polymarket_account
                    eq = float(get_polymarket_account().get("cash_balance_usd", 0) or 0)
                elif source == "kalshi":
                    from tools.account_tool import get_kalshi_balance
                    kb = get_kalshi_balance()
                    eq = float(kb.get("cash_balance_usd", 0) or 0) if not kb.get("error") else 0.0
                else:
                    eq = 0.0
            except Exception:
                eq = 0.0

            # Current NET open exposure (actual position value), not gross order flow
            try:
                if source == "polymarket":
                    from tools.account_tool import get_polymarket_positions as _gpp
                    open_exp = float(_gpp().get("portfolio_value_usd", 0) or 0)
                elif source == "kalshi":
                    from tools.account_tool import get_kalshi_balance as _gkb
                    open_exp = float(_gkb().get("positions_value_usd", 0) or 0)
                else:
                    open_exp = 0.0
            except Exception:
                open_exp = 0.0

            # Exposure cap = equity × EXPOSURE_MULTIPLIER (default 1.5x).
            # With NET exposure tracking, 1.5x means we can hold positions
            # worth 1.5x our cash — plenty for a prediction market book.
            mult = float(os.getenv("EXPOSURE_MULTIPLIER", "1.5"))
            max_exposure = float(os.getenv(
                "MAX_TOTAL_EXPOSURE_USD", str(max(200.0, eq * mult))
            ))
            sized = kelly_size_usd(
                exchange=source, price=float(price), score=score,
                ai_confidence=ai_conf, equity_usd=eq, open_exposure_usd=open_exp,
                max_total_exposure_usd=max_exposure,
                signal=sig,
            )
            size_usd = sized["size_usd"]
            if size_usd <= 0:
                logger.info("engine.execute.skip_sizing", extra={
                    "market_id": mid, "reason": sized["reason"], "score": score,
                    "ai_conf": ai_conf, "equity": eq, "open_exp": open_exp,
                })
                continue

            # ── Fee-aware gate (post-sizing) ──
            rt_fee = round_trip_fee(source, size_usd, float(price))
            expected_edge_pct = sized["inputs"].get("edge", 0.0)
            expected_gross = size_usd * expected_edge_pct
            if expected_gross <= rt_fee * 1.5:
                logger.info("engine.execute.skip_fee", extra={
                    "market_id": mid, "exchange": source, "rt_fee": round(rt_fee, 3),
                    "expected_gross": round(expected_gross, 3), "score": score,
                    "size_usd": size_usd,
                })
                continue
            logger.info("engine.execute.sized", extra={
                "market_id": mid, "size_usd": size_usd, "score": score,
                "ai_conf": ai_conf, "edge_pct": round(expected_edge_pct, 4),
                "equity": eq,
            })

            # Paper-trade mode: strategy is under evaluation. Record a virtual
            # fill at market price but never call the exchange.
            is_paper = bool(sig.get("paper_trade"))
            if is_paper:
                order_result = {
                    "order_id": str(uuid.uuid4()),
                    "status": "paper",
                    "exchange_order_id": "",
                    "error": None,
                }
                logger.info("engine.execute.paper", extra={
                    "market_id": mid, "side": side, "price": float(price),
                    "size_usd": size_usd, "strategy": sig.get("strategy_name"),
                })
            else:
                order_result = place_order(
                    exchange=source,
                    market_id=mid,
                    side=side,
                    price=float(price),
                    size_usd=size_usd,
                    ticker=ticker,
                    token_id=token_id,
                    current_exposure_usd=0.0,
                )

            order_rec = {
                "order_id": order_result.get("order_id", str(uuid.uuid4())),
                "exchange": source,
                "market_id": mid,
                "title": title[:80],
                "side": side,
                "price": float(price),
                "size_usd": size_usd,
                "status": order_result.get("status", "unknown"),
                "exchange_order_id": order_result.get("exchange_order_id", ""),
                "dry_run": DRY_RUN,
                "paper_trade": 1 if is_paper else 0,
                "error": order_result.get("error"),
                "timestamp": _now(),
            }
            try:
                insert_order(order_rec)
            except Exception:
                pass

            recent_market_ids.add(mid)
            if is_paper:
                paper_placed += 1
            else:
                orders_placed += 1
            logger.info("engine.execute.order", extra={
                "market_id": mid, "side": side, "status": order_rec["status"],
                "dry_run": DRY_RUN, "paper": is_paper,
                "paper_reason": sig.get("paper_reason"),
            })

        logger.info("engine.execute.done", extra={
            "orders_placed": orders_placed, "paper_placed": paper_placed,
            "dry_run": DRY_RUN,
        })
    else:
        logger.debug("engine.execute.disabled", extra={"auto_execute": False})

    save_checkpoint("execute_done", {**state, "orders_placed": orders_placed}, run_id)

    # ── STAGE 9: Final Checkpoint ────────────────────────────
    state["stage"] = "complete"
    cp_id = save_checkpoint("pipeline_complete", {
        **state,
        "markets": len(markets),
        "signals": len(all_forward),
        "ranked": len(ranked),
        "alerts": alerts_sent,
    }, run_id)

    append_audit_log("pipeline_complete", "engine", {
        "run_id": run_id,
        "markets": len(markets),
        "signals": len(all_forward),
        "ranked": len(ranked),
        "orders_placed": orders_placed,
    })

    result = {
        "run_id": run_id,
        "markets_scanned": len(markets),
        "signals_generated": len(all_forward),
        "ranked_signals": ranked,
        "alerts_sent": alerts_sent,
        "orders_placed": orders_placed,
        "checkpoint_id": cp_id,
        "timestamp": _now(),
    }

    logger.info("engine.pipeline.complete", extra={
        "markets": len(markets), "signals": len(all_forward),
        "ranked": len(ranked), "alerts": alerts_sent, "orders": orders_placed,
    })
    return result
