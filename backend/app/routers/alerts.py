from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session, joinedload

from ..core.security import require_analyst, require_viewer
from ..database import get_db
from ..models import Alert, AlertStatus, User
from ..schemas import AlertOut, AlertStatusUpdate
from ..services.audit import audit

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertOut])
def list_alerts(
    db: Session = Depends(get_db),
    user: User = Depends(require_viewer),
    status: Optional[AlertStatus] = None,
    customer_id: Optional[str] = Query(default=None, max_length=64),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    q = db.query(Alert).options(joinedload(Alert.transaction))
    if status:
        q = q.filter(Alert.status == status)
    if customer_id:
        q = q.filter(Alert.customer_id == customer_id)
    return q.order_by(desc(Alert.created_at)).offset(offset).limit(limit).all()


@router.get("/{alert_id}", response_model=AlertOut)
def get_alert(alert_id: int, db: Session = Depends(get_db), user: User = Depends(require_viewer)):
    alert = (
        db.query(Alert).options(joinedload(Alert.transaction)).filter(Alert.id == alert_id).first()
    )
    if alert is None:
        raise HTTPException(404, "Alert not found")
    return alert


@router.patch("/{alert_id}/status", response_model=AlertOut)
def update_alert_status(
    alert_id: int,
    payload: AlertStatusUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_analyst),
):
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(404, "Alert not found")
    old = alert.status.value
    alert.status = payload.status
    db.commit()
    db.refresh(alert)
    audit(db, user, "alert_status_changed", f"alert:{alert_id}",
          {"from": old, "to": payload.status.value})
    return alert
