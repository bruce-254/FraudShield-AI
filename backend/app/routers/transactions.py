from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import desc
from sqlalchemy.orm import Session

from ..core.security import require_analyst, require_viewer
from ..database import get_db
from ..models import Transaction, User
from ..schemas import IngestResult, TransactionIn, TransactionOut
from ..services.audit import audit
from ..services.ingestion import ingest_batch, ingest_transaction, parse_csv
from ..services.risk import score_transaction

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


@router.post("", response_model=TransactionOut, status_code=201)
def ingest_one(
    payload: TransactionIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_analyst),
):
    try:
        txn, alert = ingest_transaction(db, payload)
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    audit(db, user, "transaction_ingested", f"transaction:{txn.transaction_id}",
          {"alert_created": alert is not None})
    return txn


@router.post("/batch", response_model=IngestResult)
def ingest_batch_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_analyst),
):
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(400, "Expected a .csv file")
    content = file.file.read()
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(413, "File too large (max 20 MB)")
    try:
        rows = parse_csv(content)
    except Exception:
        raise HTTPException(400, "Could not parse CSV")
    result = ingest_batch(db, rows)
    audit(db, user, "batch_ingested", f"file:{file.filename}", result | {"errors": len(result["errors"])})
    return result


@router.get("", response_model=list[TransactionOut])
def list_transactions(
    db: Session = Depends(get_db),
    user: User = Depends(require_viewer),
    customer_id: Optional[str] = Query(default=None, max_length=64),
    min_risk: Optional[float] = Query(default=None, ge=0, le=100),
    risk_level: Optional[str] = Query(default=None, pattern="^(low|medium|high|critical)$"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    q = db.query(Transaction)
    if customer_id:
        q = q.filter(Transaction.customer_id == customer_id)
    if min_risk is not None:
        q = q.filter(Transaction.risk_score >= min_risk)
    if risk_level:
        q = q.filter(Transaction.risk_level == risk_level)
    return q.order_by(desc(Transaction.timestamp)).offset(offset).limit(limit).all()


@router.get("/{transaction_id}", response_model=TransactionOut)
def get_transaction(
    transaction_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_viewer),
):
    txn = db.query(Transaction).filter(Transaction.transaction_id == transaction_id).first()
    if txn is None:
        raise HTTPException(404, "Transaction not found")
    return txn


@router.post("/score-preview")
def score_preview(
    payload: TransactionIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_analyst),
):
    """Score a transaction WITHOUT persisting it (what-if analysis)."""
    txn_dict = payload.model_dump()
    txn_dict["channel"] = payload.channel.value
    txn_dict["status"] = payload.status.value
    result = score_transaction(db, txn_dict)
    return {"score": result["score"], "level": result["level"], "factors": result["factors"]}
