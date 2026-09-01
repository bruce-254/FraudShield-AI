from sqlalchemy.orm import Session

from ..models import AuditLog, User


def audit(db: Session, user: User | None, action: str, resource: str, detail: dict | None = None) -> None:
    """Persist an audit trail entry. Detail must never contain sensitive data."""
    entry = AuditLog(
        user_id=user.id if user else None,
        username=user.username if user else "anonymous",
        action=action,
        resource=resource,
        detail=detail or {},
    )
    db.add(entry)
    db.commit()
