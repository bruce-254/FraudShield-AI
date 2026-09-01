import csv
import io
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from ..core.security import require_analyst, require_viewer
from ..database import get_db
from ..models import Alert, AuditLog, Case, CaseStatus, Transaction, User
from ..schemas import AuditLogOut
from ..services.audit import audit

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/fraud-summary")
def fraud_summary_report(
    db: Session = Depends(get_db),
    user: User = Depends(require_viewer),
    days: int = Query(default=30, ge=1, le=365),
):
    """Aggregate fraud-operations report for the given period."""
    since = datetime.utcnow() - timedelta(days=days)
    txns = db.query(func.count(Transaction.id)).filter(Transaction.timestamp >= since).scalar() or 0
    flagged = (
        db.query(func.count(Transaction.id))
        .filter(Transaction.timestamp >= since, Transaction.risk_level.in_(["high", "critical"]))
        .scalar()
        or 0
    )
    alerts = db.query(func.count(Alert.id)).filter(Alert.created_at >= since).scalar() or 0
    cases_opened = db.query(func.count(Case.id)).filter(Case.created_at >= since).scalar() or 0
    cases_confirmed = (
        db.query(func.count(Case.id))
        .filter(Case.created_at >= since, Case.status == CaseStatus.CLOSED_CONFIRMED_FRAUD)
        .scalar()
        or 0
    )
    flagged_volume = (
        db.query(func.coalesce(func.sum(Transaction.amount), 0.0))
        .filter(Transaction.timestamp >= since, Transaction.risk_level.in_(["high", "critical"]))
        .scalar()
        or 0.0
    )
    top_rules: dict[str, int] = {}
    for (triggered,) in (
        db.query(Alert.triggered_rules).filter(Alert.created_at >= since).all()
    ):
        for hit in triggered or []:
            name = hit.get("rule_name", "unknown")
            top_rules[name] = top_rules.get(name, 0) + 1

    return {
        "period_days": days,
        "generated_at": datetime.utcnow().isoformat(),
        "transactions": txns,
        "flagged_high_or_critical": flagged,
        "flagged_rate": round(flagged / txns, 4) if txns else 0.0,
        "flagged_volume": round(float(flagged_volume), 2),
        "alerts_created": alerts,
        "cases_opened": cases_opened,
        "cases_confirmed_fraud": cases_confirmed,
        "top_triggered_rules": sorted(
            [{"rule": k, "hits": v} for k, v in top_rules.items()],
            key=lambda x: -x["hits"],
        )[:10],
    }


@router.get("/transactions.csv")
def export_transactions_csv(
    db: Session = Depends(get_db),
    user: User = Depends(require_analyst),
    days: int = Query(default=30, ge=1, le=365),
    min_risk: float = Query(default=0.0, ge=0, le=100),
):
    since = datetime.utcnow() - timedelta(days=days)
    rows = (
        db.query(Transaction)
        .filter(Transaction.timestamp >= since, Transaction.risk_score >= min_risk)
        .order_by(desc(Transaction.timestamp))
        .limit(50_000)
        .all()
    )
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "transaction_id", "customer_id", "timestamp", "amount", "currency",
        "merchant", "location", "channel", "device", "status",
        "risk_score", "risk_level", "data_source",
    ])
    for t in rows:
        writer.writerow([
            t.transaction_id, t.customer_id, t.timestamp.isoformat(), t.amount,
            t.currency, t.merchant, t.location, t.channel.value, t.device,
            t.status.value, t.risk_score, t.risk_level, t.data_source,
        ])
    audit(db, user, "report_exported", "report:transactions.csv", {"rows": len(rows)})
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=transactions.csv"},
    )


@router.get("/audit-log", response_model=list[AuditLogOut])
def audit_log(
    db: Session = Depends(get_db),
    user: User = Depends(require_analyst),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
):
    return (
        db.query(AuditLog).order_by(desc(AuditLog.created_at)).offset(offset).limit(limit).all()
    )
