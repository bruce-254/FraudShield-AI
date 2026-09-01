from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc
from sqlalchemy.orm import Session

from ..core.security import require_analyst, require_viewer
from ..database import get_db
from ..models import MLModelRecord, User
from ..schemas import MLModelOut, TrainRequest
from ..services import ml as ml_service
from ..services.audit import audit

router = APIRouter(prefix="/api/ml", tags=["ml"])


@router.post("/train", response_model=MLModelOut, status_code=201)
def train(payload: TrainRequest, db: Session = Depends(get_db), user: User = Depends(require_analyst)):
    try:
        if payload.model_kind == "supervised":
            record = ml_service.train_supervised(db, user.username, payload.test_size)
        else:
            record = ml_service.train_anomaly(db, user.username, payload.test_size)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    audit(db, user, "model_trained", f"ml_model:{record.id}",
          {"kind": record.model_kind, "algorithm": record.algorithm, "trained_on": record.trained_on})
    return record


@router.get("/models", response_model=list[MLModelOut])
def list_models(db: Session = Depends(get_db), user: User = Depends(require_viewer)):
    return db.query(MLModelRecord).order_by(desc(MLModelRecord.trained_at)).all()


@router.get("/models/active")
def active_models(db: Session = Depends(get_db), user: User = Depends(require_viewer)):
    out = {}
    for kind in ("supervised", "anomaly"):
        rec = (
            db.query(MLModelRecord)
            .filter(MLModelRecord.model_kind == kind, MLModelRecord.is_active.is_(True))
            .order_by(desc(MLModelRecord.trained_at))
            .first()
        )
        out[kind] = MLModelOut.model_validate(rec).model_dump() if rec else None
    return out
