"""
ml/reranker.py
XGBoost-based win-probability re-ranker.

Trains on the `results` table: features per trade, label=won.
Serves probability on live signals to scale Kelly sizing:
    kelly_applied = kelly_base * (predicted_win_prob / market_implied_prob)

Gated on having >=RERANKER_MIN_SAMPLES outcomes. Below that, falls back
to prob=None (sizing.py uses Kelly-only math).

Training:
    python -m ml.reranker --train

Inference:
    from ml.reranker import predict_win_prob
    p = predict_win_prob(signal_dict)  # None if model unavailable
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from logging_config.structured_logger import get_logger
from tools.database_tool import _conn

logger = get_logger(__name__)

_MODEL_PATH = Path(os.getenv("RERANKER_MODEL_PATH", "ml/models/reranker.json"))
_MIN_SAMPLES = int(os.getenv("RERANKER_MIN_SAMPLES", "100"))
_META_PATH = _MODEL_PATH.with_suffix(".meta.json")

_FEATURES = ["score", "confidence", "entry_price", "size_usd"]
_STRATEGY_ONEHOT_LIMIT = 20  # cap strategy dimensions

_model_cache = {"model": None, "loaded": False, "strategies": []}


def _fetch_training_rows() -> list[dict]:
    """Join results + signals to get (features, label) rows."""
    with _conn() as con:
        rows = con.execute("""
            SELECT r.strategy_name, r.entry_price, r.size_usd, r.won,
                   s.score, s.confidence
            FROM results r
            LEFT JOIN signals s ON s.signal_id = r.signal_id
            WHERE r.won IS NOT NULL
              AND r.entry_price > 0
              AND s.score IS NOT NULL
              AND s.confidence IS NOT NULL
        """).fetchall()
    return [{
        "strategy": r[0] or "unknown",
        "entry_price": float(r[1] or 0),
        "size_usd": float(r[2] or 0),
        "won": int(r[3]),
        "score": float(r[4] or 0),
        "confidence": float(r[5] or 0),
    } for r in rows]


def _featurize(sample: dict, strategies: list[str]) -> list[float]:
    vec = [
        float(sample.get("score", 0)),
        float(sample.get("confidence", 0)),
        float(sample.get("entry_price", 0)),
        float(sample.get("size_usd", 0)),
    ]
    strategy = sample.get("strategy", "unknown")
    for s in strategies:
        vec.append(1.0 if strategy == s else 0.0)
    return vec


def train() -> dict:
    """Train model on available outcomes. Returns summary."""
    rows = _fetch_training_rows()
    n = len(rows)
    if n < _MIN_SAMPLES:
        return {"ok": False, "reason": f"need {_MIN_SAMPLES} samples, have {n}", "n": n}

    try:
        import xgboost as xgb
    except ImportError:
        return {"ok": False, "reason": "xgboost not installed — run: pip install xgboost"}

    from collections import Counter
    strategy_counts = Counter(r["strategy"] for r in rows)
    strategies = [s for s, _ in strategy_counts.most_common(_STRATEGY_ONEHOT_LIMIT)]

    X = [_featurize(r, strategies) for r in rows]
    y = [r["won"] for r in rows]

    params = {
        "objective": "binary:logistic",
        "max_depth": 4,
        "eta": 0.1,
        "eval_metric": "logloss",
    }
    dtrain = xgb.DMatrix(X, label=y)
    model = xgb.train(params, dtrain, num_boost_round=80)

    _MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    model.save_model(str(_MODEL_PATH))
    _META_PATH.write_text(json.dumps({
        "strategies": strategies,
        "n_train": n,
        "positive_rate": sum(y) / n,
    }, indent=2))

    logger.info("reranker.trained", extra={"n": n, "strategies": len(strategies)})
    _model_cache["loaded"] = False  # force reload
    return {"ok": True, "n": n, "model_path": str(_MODEL_PATH),
            "positive_rate": sum(y) / n}


def _load():
    if _model_cache["loaded"]:
        return
    if not _MODEL_PATH.exists() or not _META_PATH.exists():
        _model_cache["loaded"] = True  # avoid re-probing every call
        return
    try:
        import xgboost as xgb
        m = xgb.Booster()
        m.load_model(str(_MODEL_PATH))
        meta = json.loads(_META_PATH.read_text())
        _model_cache["model"] = m
        _model_cache["strategies"] = meta.get("strategies", [])
        _model_cache["loaded"] = True
        logger.info("reranker.loaded", extra={"strategies": len(meta.get("strategies", []))})
    except Exception as e:
        logger.warning("reranker.load_fail", extra={"error": str(e)})
        _model_cache["loaded"] = True


def predict_win_prob(signal: dict) -> float | None:
    """Return win probability [0..1] or None if model unavailable."""
    _load()
    m = _model_cache["model"]
    if m is None:
        return None
    try:
        import xgboost as xgb
        vec = _featurize(signal, _model_cache["strategies"])
        p = float(m.predict(xgb.DMatrix([vec]))[0])
        return max(0.01, min(0.99, p))
    except Exception as e:
        logger.warning("reranker.predict_fail", extra={"error": str(e)})
        return None


if __name__ == "__main__":
    import sys
    if "--train" in sys.argv:
        print(json.dumps(train(), indent=2))
    else:
        # Diagnostic: show sample sizes
        rows = _fetch_training_rows()
        print(f"Available training rows: {len(rows)}")
        print(f"Threshold: {_MIN_SAMPLES}")
        print(f"Model path: {_MODEL_PATH} (exists={_MODEL_PATH.exists()})")
