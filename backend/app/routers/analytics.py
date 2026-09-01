from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, desc, func
from sqlalchemy.orm import Session

from ..core.security import require_viewer
from ..database import get_db
from ..models import Alert, AlertStatus, Case, Transaction, User

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/summary")
def summary(db: Session = Depends(get_db), user: User = Depends(require_viewer)):
    now = datetime.utcnow()
    day_ago = now - timedelta(hours=24)
    total_txns = db.query(func.count(Transaction.id)).scalar() or 0
    txns_24h = db.query(func.count(Transaction.id)).filter(Transaction.timestamp >= day_ago).scalar() or 0
    volume = db.query(func.coalesce(func.sum(Transaction.amount), 0.0)).scalar() or 0.0
    volume_24h = (
        db.query(func.coalesce(func.sum(Transaction.amount), 0.0))
        .filter(Transaction.timestamp >= day_ago)
        .scalar()
        or 0.0
    )
    open_alerts = (
        db.query(func.count(Alert.id))
        .filter(Alert.status.notin_([AlertStatus.DISMISSED, AlertStatus.RESOLVED]))
        .scalar()
        or 0
    )
    total_alerts = db.query(func.count(Alert.id)).scalar() or 0
    open_cases = (
        db.query(func.count(Case.id)).filter(Case.closed_at.is_(None)).scalar() or 0
    )
    avg_risk = db.query(func.coalesce(func.avg(Transaction.risk_score), 0.0)).scalar() or 0.0
    return {
        "total_transactions": total_txns,
        "transactions_24h": txns_24h,
        "total_volume": round(float(volume), 2),
        "volume_24h": round(float(volume_24h), 2),
        "total_alerts": total_alerts,
        "open_alerts": open_alerts,
        "open_cases": open_cases,
        "avg_risk_score": round(float(avg_risk), 2),
    }


@router.get("/risk-distribution")
def risk_distribution(db: Session = Depends(get_db), user: User = Depends(require_viewer)):
    rows = (
        db.query(Transaction.risk_level, func.count(Transaction.id))
        .filter(Transaction.risk_level.isnot(None))
        .group_by(Transaction.risk_level)
        .all()
    )
    counts = {level: 0 for level in ("low", "medium", "high", "critical")}
    for level, count in rows:
        counts[level] = count
    return [{"level": k, "count": v} for k, v in counts.items()]


@router.get("/high-risk-customers")
def high_risk_customers(
    db: Session = Depends(get_db),
    user: User = Depends(require_viewer),
    limit: int = Query(default=10, ge=1, le=50),
):
    rows = (
        db.query(
            Transaction.customer_id,
            func.avg(Transaction.risk_score).label("avg_risk"),
            func.max(Transaction.risk_score).label("max_risk"),
            func.count(Transaction.id).label("txn_count"),
            func.sum(
                case((Transaction.risk_level.in_(["high", "critical"]), 1), else_=0)
            ).label("high_risk_txns"),
        )
        .filter(Transaction.risk_score.isnot(None))
        .group_by(Transaction.customer_id)
        .order_by(desc("max_risk"), desc("avg_risk"))
        .limit(limit)
        .all()
    )
    return [
        {
            "customer_id": r.customer_id,
            "avg_risk": round(float(r.avg_risk), 2),
            "max_risk": round(float(r.max_risk), 2),
            "txn_count": r.txn_count,
            "high_risk_txns": int(r.high_risk_txns or 0),
        }
        for r in rows
    ]


@router.get("/volume-trend")
def volume_trend(
    db: Session = Depends(get_db),
    user: User = Depends(require_viewer),
    days: int = Query(default=30, ge=1, le=180),
):
    since = datetime.utcnow() - timedelta(days=days)
    rows = (
        db.query(
            func.date(Transaction.timestamp).label("day"),
            func.count(Transaction.id).label("count"),
            func.coalesce(func.sum(Transaction.amount), 0.0).label("volume"),
            func.sum(
                case((Transaction.risk_level.in_(["high", "critical"]), 1), else_=0)
            ).label("high_risk"),
        )
        .filter(Transaction.timestamp >= since)
        .group_by(func.date(Transaction.timestamp))
        .order_by("day")
        .all()
    )
    return [
        {
            "day": str(r.day),
            "count": r.count,
            "volume": round(float(r.volume), 2),
            "high_risk": int(r.high_risk or 0),
        }
        for r in rows
    ]


@router.get("/case-status")
def case_status(db: Session = Depends(get_db), user: User = Depends(require_viewer)):
    rows = db.query(Case.status, func.count(Case.id)).group_by(Case.status).all()
    return [{"status": s.value, "count": c} for s, c in rows]


@router.get("/alert-status")
def alert_status(db: Session = Depends(get_db), user: User = Depends(require_viewer)):
    rows = db.query(Alert.status, func.count(Alert.id)).group_by(Alert.status).all()
    return [{"status": s.value, "count": c} for s, c in rows]
