"""Explainable risk scoring.

The final score (0-100) blends three signal families and records the exact
contribution of every factor so analysts can see *why* a transaction scored
the way it did. When no ML model has been trained yet, the weights are
renormalised over the available signals — no fabricated model output ever
enters a score.
"""
from sqlalchemy.orm import Session

from ..config import get_settings
from . import ml as ml_service
from .features import compute_features
from .rule_engine import evaluate_rules

settings = get_settings()

ALERT_THRESHOLD = 60.0


def risk_level(score: float) -> str:
    if score >= 80:
        return "critical"
    if score >= 60:
        return "high"
    if score >= 35:
        return "medium"
    return "low"


def score_transaction(db: Session, txn: dict) -> dict:
    feats = compute_features(db, txn)
    rule_hits = evaluate_rules(db, txn, feats)

    # --- rule component: 1 - prod(1 - severity) rewards multiple hits without
    # exceeding 1.
    rule_component = 0.0
    remaining = 1.0
    for hit in rule_hits:
        remaining *= 1.0 - float(hit["severity"])
    if rule_hits:
        rule_component = 1.0 - remaining

    # --- model components (None when not trained)
    fraud_proba = ml_service.predict_fraud_probability(db, feats)
    anomaly_score = ml_service.predict_anomaly_score(db, feats)

    weights = {"rules": settings.risk_rule_weight}
    components = {"rules": rule_component}
    if fraud_proba is not None:
        weights["supervised_model"] = settings.risk_supervised_weight
        components["supervised_model"] = fraud_proba
    if anomaly_score is not None:
        weights["anomaly_model"] = settings.risk_anomaly_weight
        components["anomaly_model"] = anomaly_score

    total_w = sum(weights.values())
    score = sum(components[k] * weights[k] for k in weights) / total_w * 100.0
    score = round(min(max(score, 0.0), 100.0), 2)

    factors = {
        "components": [
            {
                "name": name,
                "raw_value": round(components[name], 4),
                "weight": round(weights[name] / total_w, 4),
                "contribution": round(components[name] * weights[name] / total_w * 100.0, 2),
            }
            for name in weights
        ],
        "rule_hits": rule_hits,
        "model_signals": {
            "supervised_fraud_probability": round(fraud_proba, 4) if fraud_proba is not None else None,
            "anomaly_score": round(anomaly_score, 4) if anomaly_score is not None else None,
        },
        "behavioral_context": {
            "amount_zscore_vs_customer": round(feats["amount_zscore_customer"], 2),
            "amount_ratio_to_avg": round(feats["amount_ratio_to_avg"], 2),
            "txn_count_last_hour": int(feats["txn_count_1h"]),
            "txn_count_last_24h": int(feats["txn_count_24h"]),
            "failed_count_last_24h": int(feats["failed_count_24h"]),
            "distinct_locations_24h": int(feats["distinct_locations_24h"]),
            "new_location": bool(feats["is_new_location"] > 0.5),
            "new_device": bool(feats["is_new_device"] > 0.5),
            "history_size": int(feats["_history_count"]),
        },
    }

    return {
        "score": score,
        "level": risk_level(score),
        "factors": factors,
        "rule_hits": rule_hits,
        "features": feats,
    }
