"""Pydantic schemas – strict input validation lives here."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from .models import (
    AlertStatus,
    CasePriority,
    CaseStatus,
    Channel,
    TransactionStatus,
    UserRole,
)

# ---------------------------------------------------------------- auth / users

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_.-]+$")
    email: EmailStr
    full_name: str = Field(default="", max_length=128)
    password: str = Field(min_length=8, max_length=128)
    role: UserRole = UserRole.VIEWER


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    email: EmailStr
    full_name: str
    role: UserRole
    is_active: bool


# ---------------------------------------------------------------- transactions

class TransactionIn(BaseModel):
    transaction_id: str = Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    customer_id: str = Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    timestamp: datetime
    amount: float = Field(gt=0, le=10_000_000)
    currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    merchant: str = Field(min_length=1, max_length=128)
    location: str = Field(min_length=1, max_length=128)
    channel: Channel
    device: str = Field(default="unknown", max_length=128)
    status: TransactionStatus

    @field_validator("timestamp")
    @classmethod
    def not_in_far_future(cls, v: datetime) -> datetime:
        v = v.replace(tzinfo=None)
        if v > datetime.utcnow().replace(microsecond=0) + __import__("datetime").timedelta(days=1):
            raise ValueError("timestamp cannot be more than 1 day in the future")
        return v


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    transaction_id: str
    customer_id: str
    timestamp: datetime
    amount: float
    currency: str
    merchant: str
    location: str
    channel: Channel
    device: str
    status: TransactionStatus
    risk_score: Optional[float] = None
    risk_level: Optional[str] = None
    risk_factors: Optional[dict] = None
    is_fraud_label: Optional[bool] = None
    data_source: str


class IngestResult(BaseModel):
    accepted: int
    rejected: int
    alerts_created: int
    errors: list[dict] = []


# ---------------------------------------------------------------------- rules

class RuleBase(BaseModel):
    name: str = Field(min_length=3, max_length=128)
    description: str = ""
    rule_type: str = Field(min_length=3, max_length=64)
    parameters: dict = {}
    severity: float = Field(default=0.5, ge=0.0, le=1.0)
    enabled: bool = True


class RuleCreate(RuleBase):
    pass


class RuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    parameters: Optional[dict] = None
    severity: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    enabled: Optional[bool] = None


class RuleOut(RuleBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: datetime


# --------------------------------------------------------------------- alerts

class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    transaction_pk: int
    customer_id: str
    risk_score: float
    risk_level: str
    triggered_rules: list
    factors: dict
    status: AlertStatus
    case_id: Optional[int] = None
    created_at: datetime
    transaction: Optional[TransactionOut] = None


class AlertStatusUpdate(BaseModel):
    status: AlertStatus


# ---------------------------------------------------------------------- cases

class CaseCreate(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    description: str = ""
    customer_id: str = Field(min_length=1, max_length=64)
    priority: CasePriority = CasePriority.MEDIUM
    alert_ids: list[int] = []


class CaseUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[CasePriority] = None
    status: Optional[CaseStatus] = None
    assigned_to_id: Optional[int] = None


class CaseNoteCreate(BaseModel):
    body: str = Field(min_length=1, max_length=10_000)


class CaseNoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    body: str
    created_at: datetime
    author: UserOut


class CaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    description: str
    customer_id: str
    status: CaseStatus
    priority: CasePriority
    opened_by: UserOut
    assigned_to: Optional[UserOut] = None
    created_at: datetime
    updated_at: datetime
    closed_at: Optional[datetime] = None
    notes: list[CaseNoteOut] = []
    alerts: list[AlertOut] = []


# ------------------------------------------------------------------------- ML

class TrainRequest(BaseModel):
    model_kind: str = Field(pattern=r"^(supervised|anomaly)$")
    test_size: float = Field(default=0.25, gt=0.05, lt=0.6)


class MLModelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    model_kind: str
    algorithm: str
    feature_names: list
    metrics: dict
    trained_on: int
    is_active: bool
    trained_at: datetime
    trained_by: str


# ---------------------------------------------------------------------- audit

class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    action: str
    resource: str
    detail: dict
    created_at: datetime
