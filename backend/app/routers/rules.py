from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..core.security import require_admin, require_viewer
from ..database import get_db
from ..models import Rule, User
from ..schemas import RuleCreate, RuleOut, RuleUpdate
from ..services.audit import audit
from ..services.rule_engine import available_rule_types

router = APIRouter(prefix="/api/rules", tags=["rules"])


@router.get("/types")
def rule_types(user: User = Depends(require_viewer)):
    return {"rule_types": available_rule_types()}


@router.get("", response_model=list[RuleOut])
def list_rules(db: Session = Depends(get_db), user: User = Depends(require_viewer)):
    return db.query(Rule).order_by(Rule.id).all()


@router.post("", response_model=RuleOut, status_code=201)
def create_rule(payload: RuleCreate, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    if payload.rule_type not in available_rule_types():
        raise HTTPException(400, f"Unknown rule_type. Available: {available_rule_types()}")
    if db.query(Rule).filter(Rule.name == payload.name).first():
        raise HTTPException(409, "Rule name already exists")
    rule = Rule(**payload.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    audit(db, user, "rule_created", f"rule:{rule.id}", {"name": rule.name})
    return rule


@router.patch("/{rule_id}", response_model=RuleOut)
def update_rule(rule_id: int, payload: RuleUpdate, db: Session = Depends(get_db),
                user: User = Depends(require_admin)):
    rule = db.get(Rule, rule_id)
    if rule is None:
        raise HTTPException(404, "Rule not found")
    changes = payload.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(rule, key, value)
    db.commit()
    db.refresh(rule)
    audit(db, user, "rule_updated", f"rule:{rule.id}", {"changes": list(changes.keys())})
    return rule


@router.delete("/{rule_id}", status_code=204)
def delete_rule(rule_id: int, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    rule = db.get(Rule, rule_id)
    if rule is None:
        raise HTTPException(404, "Rule not found")
    db.delete(rule)
    db.commit()
    audit(db, user, "rule_deleted", f"rule:{rule_id}", {"name": rule.name})
