"""Feature engineering for scoring and ML.

Features are computed per transaction against the customer's recent history
using pandas/numpy. The same feature vector feeds the rule engine context,
the supervised classifier and the anomaly detector, so online scoring and
training are consistent.
"""
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from ..models import Transaction, TransactionStatus

FEATURE_NAMES = [
    "amount",
    "log_amount",
    "hour_of_day",
    "day_of_week",
    "is_night",
    "amount_zscore_customer",
    "amount_ratio_to_avg",
    "txn_count_1h",
    "txn_count_24h",
    "failed_count_24h",
    "distinct_locations_24h",
    "distinct_devices_24h",
    "is_new_location",
    "is_new_device",
    "seconds_since_last_txn",
    "channel_online",
    "channel_mobile",
    "channel_atm",
]


def _history_frame(db: Session, customer_id: str, before: datetime, lookback_days: int = 90) -> pd.DataFrame:
    rows = (
        db.query(
            Transaction.amount,
            Transaction.timestamp,
            Transaction.location,
            Transaction.device,
            Transaction.status,
        )
        .filter(
            Transaction.customer_id == customer_id,
            Transaction.timestamp < before,
            Transaction.timestamp >= before - timedelta(days=lookback_days),
        )
        .order_by(Transaction.timestamp.desc())
        .limit(2000)
        .all()
    )
    return pd.DataFrame(rows, columns=["amount", "timestamp", "location", "device", "status"])


def compute_features(db: Session, txn: dict) -> dict:
    """Compute the feature dict for one transaction (txn is a plain dict with
    the canonical transaction fields)."""
    ts: datetime = txn["timestamp"]
    amount = float(txn["amount"])
    hist = _history_frame(db, txn["customer_id"], ts)

    hour = ts.hour
    features: dict[str, float] = {
        "amount": amount,
        "log_amount": float(np.log1p(amount)),
        "hour_of_day": float(hour),
        "day_of_week": float(ts.weekday()),
        "is_night": 1.0 if (hour < 6 or hour >= 23) else 0.0,
        "channel_online": 1.0 if txn["channel"] == "online" else 0.0,
        "channel_mobile": 1.0 if txn["channel"] == "mobile" else 0.0,
        "channel_atm": 1.0 if txn["channel"] == "atm" else 0.0,
    }

    if hist.empty:
        features.update(
            amount_zscore_customer=0.0,
            amount_ratio_to_avg=1.0,
            txn_count_1h=0.0,
            txn_count_24h=0.0,
            failed_count_24h=0.0,
            distinct_locations_24h=0.0,
            distinct_devices_24h=0.0,
            is_new_location=0.0,  # first txn: unknown baseline, don't penalise
            is_new_device=0.0,
            seconds_since_last_txn=86400.0 * 30,
        )
        features["_history_count"] = 0.0
        features["_customer_avg_amount"] = amount
        features["_customer_std_amount"] = 0.0
        return features

    amounts = hist["amount"].to_numpy(dtype=float)
    mean_amt = float(np.mean(amounts))
    std_amt = float(np.std(amounts))
    z = (amount - mean_amt) / std_amt if std_amt > 1e-9 else 0.0

    last_1h = hist[hist["timestamp"] >= ts - timedelta(hours=1)]
    last_24h = hist[hist["timestamp"] >= ts - timedelta(hours=24)]
    failed_24h = last_24h[
        last_24h["status"].isin([TransactionStatus.FAILED, TransactionStatus.DECLINED])
    ]

    known_locations = set(hist["location"].unique())
    known_devices = set(hist["device"].unique())
    last_ts = hist["timestamp"].max()

    features.update(
        amount_zscore_customer=float(np.clip(z, -10, 10)),
        amount_ratio_to_avg=float(amount / mean_amt) if mean_amt > 1e-9 else 1.0,
        txn_count_1h=float(len(last_1h)),
        txn_count_24h=float(len(last_24h)),
        failed_count_24h=float(len(failed_24h)),
        distinct_locations_24h=float(last_24h["location"].nunique()),
        distinct_devices_24h=float(last_24h["device"].nunique()),
        is_new_location=0.0 if txn["location"] in known_locations else 1.0,
        is_new_device=0.0 if txn["device"] in known_devices else 1.0,
        seconds_since_last_txn=float(max((ts - last_ts).total_seconds(), 0.0)),
    )
    features["_history_count"] = float(len(hist))
    features["_customer_avg_amount"] = mean_amt
    features["_customer_std_amount"] = std_amt
    return features


def feature_vector(features: dict) -> list[float]:
    return [float(features.get(name, 0.0)) for name in FEATURE_NAMES]
