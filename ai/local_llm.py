"""
ai/local_llm.py
Local LLM fallback via Ollama.

Used when Claude API is unavailable, rate-limited, or when LLM_LOCAL_ONLY=1.
Default model: qwen2.5:7b-instruct (best 7B for JSON + reasoning on 16GB RAM).

Integration point: ai.scorer._call_claude() wraps around this — if Claude
returns empty string (API error), _call_claude tries here before giving up.
"""
from __future__ import annotations

import os
from typing import Any

import requests

from logging_config.structured_logger import get_logger

logger = get_logger(__name__)

_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct")
_FAST_MODEL = os.getenv("OLLAMA_FAST_MODEL", "phi3:mini")
_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT_SEC", "30"))
_LOCAL_ONLY = os.getenv("LLM_LOCAL_ONLY", "0") == "1"


def is_available() -> bool:
    """Quick health check — returns True iff Ollama is reachable."""
    try:
        r = requests.get(f"{_BASE_URL}/api/tags", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def list_models() -> list[str]:
    try:
        r = requests.get(f"{_BASE_URL}/api/tags", timeout=5)
        if r.status_code != 200:
            return []
        return [m.get("name", "") for m in r.json().get("models", [])]
    except Exception:
        return []


def _resolve_model(tier: str) -> str:
    """tier 'C' or 'fast' -> phi3:mini, else qwen2.5 default."""
    if tier and tier.upper() in ("C", "FAST"):
        return _FAST_MODEL
    return _MODEL


def call(prompt: str, *, tier: str = "B", max_tokens: int = 16,
         system: str | None = None) -> str:
    """
    Generate a response. Returns "" on any failure.
    Default max_tokens=16 matches Claude scorer (it asks for integer score).
    """
    model = _resolve_model(tier)
    try:
        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"num_predict": max_tokens, "temperature": 0.1},
        }
        if system:
            payload["system"] = system
        r = requests.post(f"{_BASE_URL}/api/generate",
                          json=payload, timeout=_TIMEOUT)
        if r.status_code != 200:
            logger.warning("local_llm.bad_status",
                           extra={"status": r.status_code, "model": model})
            return ""
        data = r.json()
        return (data.get("response") or "").strip()
    except requests.Timeout:
        logger.warning("local_llm.timeout",
                       extra={"model": model, "timeout_sec": _TIMEOUT})
        return ""
    except Exception as e:
        logger.warning("local_llm.error",
                       extra={"model": model, "error": str(e)})
        return ""


def local_only() -> bool:
    """True if we should NEVER call Claude (LLM_LOCAL_ONLY=1 set)."""
    return _LOCAL_ONLY


if __name__ == "__main__":
    print(f"Ollama base: {_BASE_URL}")
    print(f"Available:   {is_available()}")
    print(f"Models:      {list_models()}")
    print(f"Primary:     {_MODEL}")
    print(f"Fast/C tier: {_FAST_MODEL}")
    print(f"Local-only:  {_LOCAL_ONLY}")
    if is_available():
        print()
        print("=== Latency test (B tier) ===")
        import time
        t0 = time.time()
        r = call("Rate this market signal 0-100: YES at 0.30, expected 0.55. "
                 "Reply with just the integer.", tier="B", max_tokens=10)
        dt = time.time() - t0
        print(f"  response: {r!r}  ({dt*1000:.0f}ms)")

        print("=== Latency test (C tier - fast) ===")
        t0 = time.time()
        r = call("Is BTC up or down if price moves from 60000 to 61000? "
                 "One word.", tier="C", max_tokens=8)
        dt = time.time() - t0
        print(f"  response: {r!r}  ({dt*1000:.0f}ms)")
