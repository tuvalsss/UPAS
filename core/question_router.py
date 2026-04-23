"""
core/question_router.py
Construct a single direct question, pause the pipeline, save checkpoint, wait for answer.
"""
from __future__ import annotations

import sys
import uuid
from datetime import datetime, timezone
from typing import Any

from tools.database_tool import append_question, record_answer
from logging_config.structured_logger import get_logger

logger = get_logger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_question(
    stage: str,
    market: dict[str, Any] | None,
    issue: str,
    options: list[str] | None = None,
) -> str:
    """
    Build a single, direct question string for the user.
    """
    market_info = ""
    if market:
        market_info = f'\nMarket: "{market.get("title", "unknown")}" [{market.get("source", "")}]'

    options_str = ""
    if options:
        options_str = "\nOptions:\n" + "\n".join(f"  {i+1}. {o}" for i, o in enumerate(options))

    return (
        f"\n{'='*60}\n"
        f"[UPAS QUESTION] Stage: {stage}{market_info}\n"
        f"Issue: {issue}{options_str}\n"
        f"{'='*60}"
    )


def ask(
    stage: str,
    issue: str,
    market: dict[str, Any] | None = None,
    options: list[str] | None = None,
    checkpoint_state: dict[str, Any] | None = None,
    non_interactive: bool = False,
) -> dict[str, Any]:
    """
    Pause the pipeline, ask the user one direct question, wait for answer.

    Args:
        stage: current pipeline stage
        issue: the specific ambiguity or conflict
        market: market context if applicable
        options: answer options to present
        checkpoint_state: state to save before asking
        non_interactive: if True, skip user prompt (returns 'skip')

    Returns:
        { question_id, question, answer, timestamp }
    """
    question_id = str(uuid.uuid4())
    question_text = build_question(stage, market, issue, options)

    # Save to DB
    try:
        append_question(
            question_id,
            question_text,
            {"stage": stage, "market_id": market.get("market_id") if market else None},
        )
    except Exception:
        pass

    # Save checkpoint if state provided
    if checkpoint_state is not None:
        try:
            from tools.checkpoint_tool import save
            save(stage, checkpoint_state)
        except Exception:
            pass

    logger.info("question_router.ask", extra={"stage": stage, "question_id": question_id})

    # Print question
    print(question_text)
    print("\nAnswer (or 'skip' to proceed with reduced confidence, 'stop' to halt): ", end="", flush=True)

    if non_interactive:
        answer = "skip"
        print(answer)
    else:
        try:
            answer = input().strip() or "skip"
        except (EOFError, KeyboardInterrupt):
            answer = "stop"
            print("\nInterrupted — pipeline halted.")

    if answer.lower() == "stop":
        logger.info("question_router.user_stopped")
        sys.exit(0)

    # Record answer
    try:
        record_answer(question_id, answer)
    except Exception:
        pass

    logger.info("question_router.answered", extra={"question_id": question_id, "answer": answer[:50]})

    return {
        "question_id": question_id,
        "question": question_text,
        "answer": answer,
        "timestamp": _now(),
        "skipped": answer.lower() == "skip",
    }
