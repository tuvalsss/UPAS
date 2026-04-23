"""
ml/trainer.py
Train XGBoost model on historical signal outcomes.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config.variables import DATABASE_PATH, ML_ENABLED
from ml.dataset import build_training_records
from ml.features import build_feature_matrix
from logging_config.structured_logger import get_logger

logger = get_logger(__name__)

_ARTIFACT_DIR = DATABASE_PATH.parent / "model_artifacts"


def train(min_outcomes: int = 50) -> dict[str, Any]:
    """
    Train XGBoost classifier on available outcomes.
    Returns training report.
    """
    if not ML_ENABLED:
        return {"success": False, "reason": "ml_enabled=false"}

    try:
        import xgboost as xgb
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import accuracy_score, roc_auc_score
    except ImportError as e:
        logger.error("trainer.import_error", extra={"error": str(e)})
        return {"success": False, "reason": str(e)}

    records = build_training_records(min_outcomes=min_outcomes)
    if not records:
        return {"success": False, "reason": f"Fewer than {min_outcomes} resolved outcomes"}

    X, y, feature_names = build_feature_matrix(records)
    if len(X) == 0:
        return {"success": False, "reason": "Empty feature matrix"}

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    model = xgb.XGBClassifier(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        eval_metric="logloss",
        random_state=42,
    )
    model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)

    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    try:
        auc = roc_auc_score(y_test, model.predict_proba(X_test)[:, 1])
    except Exception:
        auc = 0.0

    # Feature importance
    importance = dict(sorted(
        zip(feature_names, model.feature_importances_),
        key=lambda x: x[1], reverse=True,
    )[:10])

    # Save model
    _ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    artifact_id = str(uuid.uuid4())[:8]
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    model_path = _ARTIFACT_DIR / f"xgb_{ts}_{artifact_id}.json"
    model.save_model(str(model_path))

    metrics = {
        "accuracy": round(accuracy, 4),
        "auc": round(auc, 4),
        "train_samples": len(X_train),
        "test_samples": len(X_test),
        "top_features": importance,
    }

    # Log to DB
    try:
        from tools.database_tool import append_audit_log
        append_audit_log("model_trained", "ml_trainer", {
            "artifact_path": str(model_path),
            "metrics": metrics,
        })
    except Exception:
        pass

    logger.info("trainer.complete", extra=metrics)
    return {"success": True, "model_path": str(model_path), "metrics": metrics}
