from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .core.security import hash_password
from .database import Base, SessionLocal, engine
from .models import User, UserRole
from .routers import admin, alerts, analytics, auth, cases, ml, reports, rules, transactions
from .services.rule_engine import seed_default_rules

settings = get_settings()

DEFAULT_USERS = [
    # Development bootstrap accounts. Change/remove in production.
    {"username": "admin", "email": "admin@fraudshield.example", "full_name": "Admin User",
     "password": "AdminPass123!", "role": UserRole.ADMIN},
    {"username": "analyst", "email": "analyst@fraudshield.example", "full_name": "Fraud Analyst",
     "password": "AnalystPass123!", "role": UserRole.ANALYST},
    {"username": "viewer", "email": "viewer@fraudshield.example", "full_name": "Read Only",
     "password": "ViewerPass123!", "role": UserRole.VIEWER},
]


def bootstrap(db) -> None:
    seed_default_rules(db)
    if db.query(User).count() == 0:
        for spec in DEFAULT_USERS:
            db.add(
                User(
                    username=spec["username"],
                    email=spec["email"],
                    full_name=spec["full_name"],
                    hashed_password=hash_password(spec["password"]),
                    role=spec["role"],
                )
            )
        db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        bootstrap(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title="FraudShield AI",
    description="Defensive financial fraud detection & transaction analytics platform. "
                "Development data is synthetic only.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.environment == "development" else [],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(transactions.router)
app.include_router(rules.router)
app.include_router(alerts.router)
app.include_router(cases.router)
app.include_router(ml.router)
app.include_router(analytics.router)
app.include_router(reports.router)
app.include_router(admin.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "app": settings.app_name, "environment": settings.environment}
