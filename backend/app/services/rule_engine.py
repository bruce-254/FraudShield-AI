"""Configurable rule engine.

Rules live in the database (Rule model). Each rule references a *rule_type*
implemented by an evaluator in the registry below and carries its own JSON
``parameters``. Nothing about thresholds is hardcoded elsewhere in the app —
adding/tuning/disabling rules is pure data.

An evaluator receives the transaction dict, the engineered feature dict and
the rule parameters, and returns ``(hit: bool, detail: str)``.
"""
from typing import Callable

from sqlalchemy.orm import Session

from ..models import Rule

Evaluator = Callable[[dict, dict, dict], tuple[bool, str]]

_REGISTRY: dict[str, Evaluator] = {}


def rule_type(name: str):
    def deco(fn: Evaluator) -> Evaluator:
        _REGISTRY[name] = fn
        return fn

    return deco


def available_rule_types() -> list[str]:
    return sorted(_REGISTRY.keys())


# ------------------------------------------------------------- evaluators

@rule_type("unusual_amount")
def unusual_amount(txn: dict, feats: dict, params: dict) -> tuple[bool, str]:
    """Amount is a statistical outlier vs. customer history, or above an
    absolute ceiling."""
    z_threshold = float(params.get("zscore_threshold", 3.0))
    abs_threshold = float(params.get("absolute_threshold", 10_000.0))
    min_history = int(params.get("min_history", 5))

    if txn["amount"] >= abs_threshold:
        return True, f"Amount {txn['amount']:.2f} exceeds absolute threshold {abs_threshold:.2f}"
    if feats.get("_history_count", 0) >= min_history and feats["amount_zscore_customer"] >= z_threshold:
        return True, (
            f"Amount is {feats['amount_zscore_customer']:.1f} standard deviations above "
            f"this customer's average of {feats['_customer_avg_amount']:.2f}"
        )
    return False, ""


@rule_type("rapid_frequency")
def rapid_frequency(txn: dict, feats: dict, params: dict) -> tuple[bool, str]:
    max_1h = int(params.get("max_txn_per_hour", 5))
    max_24h = int(params.get("max_txn_per_day", 30))
    if feats["txn_count_1h"] >= max_1h:
        return True, f"{int(feats['txn_count_1h'])} transactions in the last hour (limit {max_1h})"
    if feats["txn_count_24h"] >= max_24h:
        return True, f"{int(feats['txn_count_24h'])} transactions in the last 24h (limit {max_24h})"
    return False, ""


@rule_type("geo_anomaly")
def geo_anomaly(txn: dict, feats: dict, params: dict) -> tuple[bool, str]:
    max_locations_24h = int(params.get("max_locations_per_day", 3))
    flag_new_location = bool(params.get("flag_new_location", True))
    min_history = int(params.get("min_history", 10))

    if feats["distinct_locations_24h"] >= max_locations_24h:
        return True, (
            f"Transactions from {int(feats['distinct_locations_24h'])} distinct locations "
            f"within 24h (limit {max_locations_24h})"
        )
    if (
        flag_new_location
        and feats.get("_history_count", 0) >= min_history
        and feats["is_new_location"] > 0.5
    ):
        return True, f"First ever transaction from location '{txn['location']}'"
    return False, ""


@rule_type("repeated_failures")
def repeated_failures(txn: dict, feats: dict, params: dict) -> tuple[bool, str]:
    max_failed_24h = int(params.get("max_failed_per_day", 3))
    if feats["failed_count_24h"] >= max_failed_24h:
        return True, (
            f"{int(feats['failed_count_24h'])} failed/declined transactions in the last 24h "
            f"(limit {max_failed_24h})"
        )
    return False, ""


@rule_type("behavior_change")
def behavior_change(txn: dict, feats: dict, params: dict) -> tuple[bool, str]:
    """Sudden behavioural change: new device plus unusual spend ratio, or
    off-hours activity for a customer with established history."""
    ratio_threshold = float(params.get("amount_ratio_threshold", 5.0))
    min_history = int(params.get("min_history", 10))
    flag_night_new_device = bool(params.get("flag_night_new_device", True))

    if feats.get("_history_count", 0) < min_history:
        return False, ""
    if feats["is_new_device"] > 0.5 and feats["amount_ratio_to_avg"] >= ratio_threshold:
        return True, (
            f"New device '{txn['device']}' with spend {feats['amount_ratio_to_avg']:.1f}x "
            "the customer's average"
        )
    if flag_night_new_device and feats["is_new_device"] > 0.5 and feats["is_night"] > 0.5:
        return True, f"Night-time transaction from previously unseen device '{txn['device']}'"
    return False, ""


# ------------------------------------------------------------- engine

def evaluate_rules(db: Session, txn: dict, feats: dict) -> list[dict]:
    """Run every enabled DB rule against the transaction. Returns hits with
    explanation and severity."""
    hits: list[dict] = []
    rules = db.query(Rule).filter(Rule.enabled.is_(True)).all()
    for rule in rules:
        evaluator = _REGISTRY.get(rule.rule_type)
        if evaluator is None:
            continue  # unknown type: skip defensively
        try:
            hit, detail = evaluator(txn, feats, rule.parameters or {})
        except Exception as exc:  # a broken rule must never break ingestion
            hit, detail = False, f"rule error: {exc}"
        if hit:
            hits.append(
                {
                    "rule_id": rule.id,
                    "rule_name": rule.name,
                    "rule_type": rule.rule_type,
                    "severity": rule.severity,
                    "detail": detail,
                }
            )
    return hits


DEFAULT_RULES = [
    {
        "name": "Unusual transaction amount",
        "description": "Amount is a statistical outlier versus the customer's own history, or above an absolute ceiling.",
        "rule_type": "unusual_amount",
        "parameters": {"zscore_threshold": 3.0, "absolute_threshold": 10000.0, "min_history": 5},
        "severity": 0.8,
    },
    {
        "name": "Rapid transaction frequency",
        "description": "Too many transactions in a short window (velocity check).",
        "rule_type": "rapid_frequency",
        "parameters": {"max_txn_per_hour": 5, "max_txn_per_day": 30},
        "severity": 0.7,
    },
    {
        "name": "Unusual geographic pattern",
        "description": "Multiple distinct locations in 24h or a first-seen location.",
        "rule_type": "geo_anomaly",
        "parameters": {"max_locations_per_day": 3, "flag_new_location": True, "min_history": 10},
        "severity": 0.6,
    },
    {
        "name": "Repeated failed transactions",
        "description": "Several failed or declined attempts within 24 hours.",
        "rule_type": "repeated_failures",
        "parameters": {"max_failed_per_day": 3},
        "severity": 0.65,
    },
    {
        "name": "Sudden behavioral change",
        "description": "New device combined with unusual spend or night-time activity.",
        "rule_type": "behavior_change",
        "parameters": {"amount_ratio_threshold": 5.0, "min_history": 10, "flag_night_new_device": True},
        "severity": 0.6,
    },
]


def seed_default_rules(db: Session) -> None:
    """Insert the default rule set if the rules table is empty."""
    if db.query(Rule).count() > 0:
        return
    for spec in DEFAULT_RULES:
        db.add(Rule(**spec))
    db.commit()
