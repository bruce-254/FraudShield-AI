import enum
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"


class TransactionStatus(str, enum.Enum):
    APPROVED = "approved"
    DECLINED = "declined"
    PENDING = "pending"
    FAILED = "failed"
    REVERSED = "reversed"


class Channel(str, enum.Enum):
    CARD_PRESENT = "card_present"
    ONLINE = "online"
    MOBILE = "mobile"
    ATM = "atm"
    POS = "pos"
    TRANSFER = "transfer"


class AlertStatus(str, enum.Enum):
    OPEN = "open"
    IN_REVIEW = "in_review"
    ESCALATED = "escalated"
    DISMISSED = "dismissed"
    RESOLVED = "resolved"


class CaseStatus(str, enum.Enum):
    OPEN = "open"
    ASSIGNED = "assigned"
    INVESTIGATING = "investigating"
    PENDING_INFO = "pending_info"
    CLOSED_CONFIRMED_FRAUD = "closed_confirmed_fraud"
    CLOSED_FALSE_POSITIVE = "closed_false_positive"
    CLOSED_INCONCLUSIVE = "closed_inconclusive"


class CasePriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    full_name: Mapped[str] = mapped_column(String(128), default="")
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.VIEWER)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    transaction_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    customer_id: Mapped[str] = mapped_column(String(64), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True)
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(8))
    merchant: Mapped[str] = mapped_column(String(128))
    location: Mapped[str] = mapped_column(String(128))
    channel: Mapped[Channel] = mapped_column(Enum(Channel))
    device: Mapped[str] = mapped_column(String(128), default="unknown")
    status: Mapped[TransactionStatus] = mapped_column(Enum(TransactionStatus))

    # Analytics / scoring output
    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_level: Mapped[str | None] = mapped_column(String(16), nullable=True)
    risk_factors: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Ground-truth label when known (synthetic data / closed investigations).
    is_fraud_label: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    # Provenance flag – synthetic development data is clearly marked.
    data_source: Mapped[str] = mapped_column(String(32), default="ingested")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    alerts: Mapped[list["Alert"]] = relationship(back_populates="transaction")

    __table_args__ = (Index("ix_txn_customer_ts", "customer_id", "timestamp"),)


class Rule(Base):
    __tablename__ = "rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    rule_type: Mapped[str] = mapped_column(String(64), index=True)
    parameters: Mapped[dict] = mapped_column(JSON, default=dict)
    severity: Mapped[float] = mapped_column(Float, default=0.5)  # 0..1 contribution weight
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    transaction_pk: Mapped[int] = mapped_column(ForeignKey("transactions.id"), index=True)
    customer_id: Mapped[str] = mapped_column(String(64), index=True)
    risk_score: Mapped[float] = mapped_column(Float)
    risk_level: Mapped[str] = mapped_column(String(16))
    triggered_rules: Mapped[list] = mapped_column(JSON, default=list)
    factors: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[AlertStatus] = mapped_column(Enum(AlertStatus), default=AlertStatus.OPEN)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    transaction: Mapped["Transaction"] = relationship(back_populates="alerts")
    case_id: Mapped[int | None] = mapped_column(ForeignKey("cases.id"), nullable=True)


class Case(Base):
    __tablename__ = "cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    customer_id: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[CaseStatus] = mapped_column(Enum(CaseStatus), default=CaseStatus.OPEN)
    priority: Mapped[CasePriority] = mapped_column(Enum(CasePriority), default=CasePriority.MEDIUM)
    opened_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    assigned_to_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    opened_by: Mapped["User"] = relationship(foreign_keys=[opened_by_id])
    assigned_to: Mapped["User | None"] = relationship(foreign_keys=[assigned_to_id])
    notes: Mapped[list["CaseNote"]] = relationship(back_populates="case", order_by="CaseNote.created_at")
    alerts: Mapped[list["Alert"]] = relationship()


class CaseNote(Base):
    __tablename__ = "case_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    case: Mapped["Case"] = relationship(back_populates="notes")
    author: Mapped["User"] = relationship()


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    username: Mapped[str] = mapped_column(String(64), default="anonymous")
    action: Mapped[str] = mapped_column(String(64), index=True)
    resource: Mapped[str] = mapped_column(String(128))
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class MLModelRecord(Base):
    """Metadata of trained models. Metrics stored here are always computed on a
    real held-out evaluation split – never fabricated."""

    __tablename__ = "ml_models"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    model_kind: Mapped[str] = mapped_column(String(32))  # 'supervised' | 'anomaly'
    algorithm: Mapped[str] = mapped_column(String(64))
    artifact_path: Mapped[str] = mapped_column(String(255))
    feature_names: Mapped[list] = mapped_column(JSON, default=list)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    trained_on: Mapped[int] = mapped_column(Integer, default=0)  # sample count
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    trained_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    trained_by: Mapped[str] = mapped_column(String(64), default="system")
