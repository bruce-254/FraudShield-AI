import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["FRAUDSHIELD_DATABASE_URL"] = "sqlite://"  # in-memory per test session
os.environ["FRAUDSHIELD_SECRET_KEY"] = "test-secret"
os.environ["FRAUDSHIELD_ML_ARTIFACT_DIR"] = "/tmp/fraudshield_test_artifacts"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import database
from app.database import Base
import app.main as main_module
from app.main import app, bootstrap

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Point the app's database module at the test engine.
database.engine = engine
database.SessionLocal = TestingSessionLocal
main_module.engine = engine
main_module.SessionLocal = TestingSessionLocal


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[database.get_db] = override_get_db


@pytest.fixture(scope="function")
def client():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    bootstrap(db)
    db.close()
    with TestClient(app) as c:
        yield c


def login(client: TestClient, username: str, password: str) -> dict:
    resp = client.post("/api/auth/login", data={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture
def admin_headers(client):
    return login(client, "admin", "AdminPass123!")


@pytest.fixture
def analyst_headers(client):
    return login(client, "analyst", "AnalystPass123!")


@pytest.fixture
def viewer_headers(client):
    return login(client, "viewer", "ViewerPass123!")


def make_txn(**overrides) -> dict:
    from datetime import datetime

    base = {
        "transaction_id": overrides.pop("transaction_id", "TXN-0001"),
        "customer_id": "CUST-001",
        "timestamp": datetime.utcnow().isoformat(),
        "amount": 50.0,
        "currency": "USD",
        "merchant": "GrocerMart",
        "location": "New York-US",
        "channel": "card_present",
        "device": "web-chrome",
        "status": "approved",
    }
    base.update(overrides)
    return base
