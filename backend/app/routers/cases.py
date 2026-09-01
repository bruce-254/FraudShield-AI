from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session, joinedload

from ..core.security import require_analyst, require_viewer
from ..database import get_db
from ..models import Alert, AlertStatus, Case, CaseNote, CaseStatus, User
from ..schemas import CaseCreate, CaseNoteCreate, CaseOut, CaseUpdate
from ..services.audit import audit

router = APIRouter(prefix="/api/cases", tags=["cases"])

CLOSED_STATUSES = {
    CaseStatus.CLOSED_CONFIRMED_FRAUD,
    CaseStatus.CLOSED_FALSE_POSITIVE,
    CaseStatus.CLOSED_INCONCLUSIVE,
}


def _load_case(db: Session, case_id: int) -> Case:
    case = (
        db.query(Case)
        .options(
            joinedload(Case.notes).joinedload(CaseNote.author),
            joinedload(Case.alerts).joinedload(Alert.transaction),
            joinedload(Case.opened_by),
            joinedload(Case.assigned_to),
        )
        .filter(Case.id == case_id)
        .first()
    )
    if case is None:
        raise HTTPException(404, "Case not found")
    return case


@router.post("", response_model=CaseOut, status_code=201)
def open_case(payload: CaseCreate, db: Session = Depends(get_db), user: User = Depends(require_analyst)):
    case = Case(
        title=payload.title,
        description=payload.description,
        customer_id=payload.customer_id,
        priority=payload.priority,
        opened_by_id=user.id,
    )
    db.add(case)
    db.flush()
    for alert_id in payload.alert_ids:
        alert = db.get(Alert, alert_id)
        if alert is None:
            raise HTTPException(404, f"Alert {alert_id} not found")
        alert.case_id = case.id
        if alert.status == AlertStatus.OPEN:
            alert.status = AlertStatus.IN_REVIEW
    db.commit()
    audit(db, user, "case_opened", f"case:{case.id}",
          {"customer_id": payload.customer_id, "alerts": payload.alert_ids})
    return _load_case(db, case.id)


@router.get("", response_model=list[CaseOut])
def list_cases(
    db: Session = Depends(get_db),
    user: User = Depends(require_viewer),
    status: Optional[CaseStatus] = None,
    assigned_to_id: Optional[int] = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    q = db.query(Case).options(
        joinedload(Case.opened_by), joinedload(Case.assigned_to),
        joinedload(Case.notes).joinedload(CaseNote.author),
        joinedload(Case.alerts).joinedload(Alert.transaction),
    )
    if status:
        q = q.filter(Case.status == status)
    if assigned_to_id:
        q = q.filter(Case.assigned_to_id == assigned_to_id)
    return q.order_by(desc(Case.updated_at)).offset(offset).limit(limit).all()


@router.get("/{case_id}", response_model=CaseOut)
def get_case(case_id: int, db: Session = Depends(get_db), user: User = Depends(require_viewer)):
    return _load_case(db, case_id)


@router.patch("/{case_id}", response_model=CaseOut)
def update_case(case_id: int, payload: CaseUpdate, db: Session = Depends(get_db),
                user: User = Depends(require_analyst)):
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(404, "Case not found")
    changes = payload.model_dump(exclude_unset=True)

    if "assigned_to_id" in changes and changes["assigned_to_id"] is not None:
        assignee = db.get(User, changes["assigned_to_id"])
        if assignee is None:
            raise HTTPException(404, "Assignee not found")
        if case.status == CaseStatus.OPEN:
            case.status = CaseStatus.ASSIGNED

    for key, value in changes.items():
        setattr(case, key, value)

    if case.status in CLOSED_STATUSES and case.closed_at is None:
        case.closed_at = datetime.utcnow()
        for alert in db.query(Alert).filter(Alert.case_id == case.id).all():
            alert.status = (
                AlertStatus.RESOLVED
                if case.status == CaseStatus.CLOSED_CONFIRMED_FRAUD
                else AlertStatus.DISMISSED
            )
    db.commit()
    audit(db, user, "case_updated", f"case:{case_id}", {"changes": list(changes.keys())})
    return _load_case(db, case_id)


@router.post("/{case_id}/notes", response_model=CaseOut, status_code=201)
def add_note(case_id: int, payload: CaseNoteCreate, db: Session = Depends(get_db),
             user: User = Depends(require_analyst)):
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(404, "Case not found")
    db.add(CaseNote(case_id=case_id, author_id=user.id, body=payload.body))
    case.updated_at = datetime.utcnow()
    db.commit()
    audit(db, user, "case_note_added", f"case:{case_id}")
    return _load_case(db, case_id)
