"""Admin utilities: seed SYNTHETIC development data. Clearly labeled synthetic;
never real payment data."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..core.security import require_admin
from ..database import get_db
from ..models import User
from ..services.audit import audit
from ..services.ingestion import ingest_batch
from ..services.synthetic import generate_synthetic_dataset

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post("/seed-synthetic")
def seed_synthetic(
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
    customers: int = Query(default=40, ge=5, le=200),
    days: int = Query(default=45, ge=7, le=180),
    seed: int = Query(default=7),
):
    rows = generate_synthetic_dataset(n_customers=customers, days=days, seed=seed)
    payload = [dict(r) for r in rows]
    result = ingest_batch(db, payload, data_source="synthetic")
    audit(db, user, "synthetic_seeded", "dataset:synthetic",
          {"customers": customers, "days": days, **{k: result[k] for k in ("accepted", "rejected", "alerts_created")}})
    return {"note": "SYNTHETIC development data — not real financial data", **result}
