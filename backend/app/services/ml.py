"""ML training and inference.

- Supervised classification (RandomForest) when labelled data exists.
- Unsupervised anomaly detection (IsolationForest) when it does not.

All reported metrics (precision / recall / F1 / ROC-AUC / confusion matrix)
are computed on a genuine held-out test split. Nothing is fabricated; if
there is not enough data to train, training fails loudly.
"""
import os
import uuid
from datetime import datetime

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.metrics import (
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import MLModelRecord, Transaction
from .features import FEATURE_NAMES, compute_features, feature_vector

settings = get_settings()

_model_cache: dict[str, tuple[int, object]] = {}


def _artifact_dir() -> str:
    os.makedirs(settings.ml_artifact_dir, exist_ok=True)
    return settings.ml_artifact_dir


def _build_dataset(db: Session, labeled_only: bool) -> tuple[np.ndarray, np.ndarray, int]:
    """Recompute features for stored transactions. Returns X, y, n."""
    q = db.query(Transaction).order_by(Transaction.timestamp.asc())
    if labeled_only:
        q = q.filter(Transaction.is_fraud_label.isnot(None))
    txns = q.all()

    X, y = [], []
    for t in txns:
        txn_dict = {
            "customer_id": t.customer_id,
            "timestamp": t.timestamp,
            "amount": t.amount,
            "currency": t.currency,
            "merchant": t.merchant,
            "location": t.location,
            "channel": t.channel.value,
            "device": t.device,
            "status": t.status.value,
        }
        feats = compute_features(db, txn_dict)
        X.append(feature_vector(feats))
        y.append(1 if t.is_fraud_label else 0)
    return np.asarray(X, dtype=float), np.asarray(y, dtype=int), len(txns)


def train_supervised(db: Session, trained_by: str, test_size: float = 0.25) -> MLModelRecord:
    X, y, n = _build_dataset(db, labeled_only=True)
    if n < 50:
        raise ValueError(f"Need at least 50 labelled transactions to train (have {n}).")
    if len(np.unique(y)) < 2:
        raise ValueError("Labelled data contains only one class; cannot train a classifier.")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=42, stratify=y
    )

    clf = RandomForestClassifier(
        n_estimators=300,
        max_depth=None,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )
    clf.fit(X_train, y_train)

    y_pred = clf.predict(X_test)
    y_proba = clf.predict_proba(X_test)[:, 1]

    cm = confusion_matrix(y_test, y_pred).tolist()
    metrics = {
        "precision": round(float(precision_score(y_test, y_pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y_test, y_pred, zero_division=0)), 4),
        "f1": round(float(f1_score(y_test, y_pred, zero_division=0)), 4),
        "roc_auc": round(float(roc_auc_score(y_test, y_proba)), 4),
        "confusion_matrix": cm,
        "test_size": len(y_test),
        "train_size": len(y_train),
        "positive_rate": round(float(np.mean(y)), 4),
        "feature_importances": {
            name: round(float(imp), 4)
            for name, imp in sorted(
                zip(FEATURE_NAMES, clf.feature_importances_), key=lambda p: -p[1]
            )[:10]
        },
    }

    path = os.path.join(_artifact_dir(), f"supervised_{uuid.uuid4().hex[:8]}.joblib")
    joblib.dump({"model": clf, "feature_names": FEATURE_NAMES}, path)

    db.query(MLModelRecord).filter(MLModelRecord.model_kind == "supervised").update(
        {"is_active": False}
    )
    record = MLModelRecord(
        model_kind="supervised",
        algorithm="RandomForestClassifier",
        artifact_path=path,
        feature_names=FEATURE_NAMES,
        metrics=metrics,
        trained_on=n,
        trained_by=trained_by,
        is_active=True,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    _model_cache.pop("supervised", None)
    return record


def train_anomaly(db: Session, trained_by: str, test_size: float = 0.25) -> MLModelRecord:
    X, y, n = _build_dataset(db, labeled_only=False)
    if n < 50:
        raise ValueError(f"Need at least 50 transactions to fit the anomaly detector (have {n}).")

    model = IsolationForest(n_estimators=200, contamination="auto", random_state=42)
    model.fit(X)

    metrics: dict = {"fitted_on": n}
    # If labels happen to exist we honestly evaluate the detector against them.
    labeled_mask = np.array(
        [t.is_fraud_label is not None for t in db.query(Transaction).order_by(Transaction.timestamp.asc()).all()]
    )
    if labeled_mask.any() and len(np.unique(y[labeled_mask])) == 2:
        scores = -model.score_samples(X[labeled_mask])  # higher = more anomalous
        y_true = y[labeled_mask]
        try:
            metrics["roc_auc_vs_labels"] = round(float(roc_auc_score(y_true, scores)), 4)
        except ValueError:
            pass
        preds = (model.predict(X[labeled_mask]) == -1).astype(int)
        metrics["precision_vs_labels"] = round(float(precision_score(y_true, preds, zero_division=0)), 4)
        metrics["recall_vs_labels"] = round(float(recall_score(y_true, preds, zero_division=0)), 4)
        metrics["f1_vs_labels"] = round(float(f1_score(y_true, preds, zero_division=0)), 4)
        metrics["confusion_matrix_vs_labels"] = confusion_matrix(y_true, preds).tolist()

    # Calibration bounds so online scores can be mapped to 0..1.
    raw = -model.score_samples(X)
    metrics["score_p05"] = float(np.percentile(raw, 5))
    metrics["score_p99"] = float(np.percentile(raw, 99))

    path = os.path.join(_artifact_dir(), f"anomaly_{uuid.uuid4().hex[:8]}.joblib")
    joblib.dump(
        {
            "model": model,
            "feature_names": FEATURE_NAMES,
            "score_p05": metrics["score_p05"],
            "score_p99": metrics["score_p99"],
        },
        path,
    )

    db.query(MLModelRecord).filter(MLModelRecord.model_kind == "anomaly").update(
        {"is_active": False}
    )
    record = MLModelRecord(
        model_kind="anomaly",
        algorithm="IsolationForest",
        artifact_path=path,
        feature_names=FEATURE_NAMES,
        metrics=metrics,
        trained_on=n,
        trained_by=trained_by,
        is_active=True,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    _model_cache.pop("anomaly", None)
    return record


def _load_active(db: Session, kind: str):
    record = (
        db.query(MLModelRecord)
        .filter(MLModelRecord.model_kind == kind, MLModelRecord.is_active.is_(True))
        .order_by(MLModelRecord.trained_at.desc())
        .first()
    )
    if record is None or not os.path.exists(record.artifact_path):
        return None
    cached = _model_cache.get(kind)
    if cached and cached[0] == record.id:
        return cached[1]
    bundle = joblib.load(record.artifact_path)
    _model_cache[kind] = (record.id, bundle)
    return bundle


def predict_fraud_probability(db: Session, feats: dict) -> float | None:
    """Real model inference; returns None when no trained model exists."""
    bundle = _load_active(db, "supervised")
    if bundle is None:
        return None
    X = np.asarray([feature_vector(feats)], dtype=float)
    return float(bundle["model"].predict_proba(X)[0, 1])


def predict_anomaly_score(db: Session, feats: dict) -> float | None:
    """Normalised 0..1 anomaly score; None when no trained detector exists."""
    bundle = _load_active(db, "anomaly")
    if bundle is None:
        return None
    X = np.asarray([feature_vector(feats)], dtype=float)
    raw = float(-bundle["model"].score_samples(X)[0])
    lo, hi = bundle.get("score_p05", 0.3), bundle.get("score_p99", 0.7)
    if hi - lo < 1e-9:
        return 0.5
    return float(np.clip((raw - lo) / (hi - lo), 0.0, 1.0))
