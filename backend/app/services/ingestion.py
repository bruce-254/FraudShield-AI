"""Transaction ingestion: validate → persist → score → alert."""
import csv
import io
from datetime import datetime

from pydantic import ValidationError
from sqlalchemy.orm import Session

from ..models import Alert, Transaction
from ..schemas import TransactionIn
from .risk import ALERT_THRESHOLD, score_transaction


def ingest_transaction(db: Session, payload: TransactionIn, data_source: str = "ingested",
                       is_fraud_label: bool | None = None) -> tuple[Transaction, Alert | None]:
    """Persist a validated transaction, score it and raise an alert when the
    risk score crosses the alert threshold."""
    existing = (
        db.query(Transaction)
        .filter(Transaction.transaction_id == payload.transaction_id)
        .first()
    )
    if existing is not None:
        raise ValueError(f"transaction_id '{payload.transaction_id}' already exists")

    txn_dict = payload.model_dump()
    txn_dict["channel"] = payload.channel.value
    txn_dict["status"] = payload.status.value

    result = score_transaction(db, txn_dict)

    txn = Transaction(
        transaction_id=payload.transaction_id,
        customer_id=payload.customer_id,
        timestamp=payload.timestamp.replace(tzinfo=None),
        amount=payload.amount,
        currency=payload.currency,
        merchant=payload.merchant,
        location=payload.location,
        channel=payload.channel,
        device=payload.device,
        status=payload.status,
        risk_score=result["score"],
        risk_level=result["level"],
        risk_factors=result["factors"],
        data_source=data_source,
        is_fraud_label=is_fraud_label,
    )
    db.add(txn)
    db.flush()

    alert = None
    if result["score"] >= ALERT_THRESHOLD:
        alert = Alert(
            transaction_pk=txn.id,
            customer_id=txn.customer_id,
            risk_score=result["score"],
            risk_level=result["level"],
            triggered_rules=result["rule_hits"],
            factors=result["factors"],
        )
        db.add(alert)

    db.commit()
    db.refresh(txn)
    return txn, alert


def ingest_batch(db: Session, rows: list[dict], data_source: str = "ingested") -> dict:
    accepted = rejected = alerts_created = 0
    errors: list[dict] = []
    for i, row in enumerate(rows):
        label = row.pop("is_fraud_label", None)
        if isinstance(label, str):
            label = label.strip().lower() in {"1", "true", "yes"} if label.strip() else None
        try:
            payload = TransactionIn(**row)
            _, alert = ingest_transaction(db, payload, data_source=data_source, is_fraud_label=label)
            accepted += 1
            if alert is not None:
                alerts_created += 1
        except (ValidationError, ValueError) as exc:
            rejected += 1
            if len(errors) < 50:
                errors.append({"row": i, "error": str(exc)[:500]})
    return {
        "accepted": accepted,
        "rejected": rejected,
        "alerts_created": alerts_created,
        "errors": errors,
    }


def parse_csv(content: bytes) -> list[dict]:
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    return [dict(r) for r in reader]
