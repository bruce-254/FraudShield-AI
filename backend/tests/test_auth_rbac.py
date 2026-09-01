"""Authentication, authorization (RBAC) and audit logging tests."""
from .conftest import login, make_txn


def test_login_success_and_me(client):
    headers = login(client, "admin", "AdminPass123!")
    resp = client.get("/api/auth/me", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["role"] == "admin"


def test_login_wrong_password(client):
    resp = client.post("/api/auth/login", data={"username": "admin", "password": "wrong"})
    assert resp.status_code == 401


def test_unauthenticated_access_blocked(client):
    assert client.get("/api/transactions").status_code == 401
    assert client.get("/api/alerts").status_code == 401
    assert client.get("/api/cases").status_code == 401


def test_viewer_cannot_ingest(client, viewer_headers):
    resp = client.post("/api/transactions", json=make_txn(), headers=viewer_headers)
    assert resp.status_code == 403


def test_analyst_cannot_manage_rules(client, analyst_headers):
    resp = client.post(
        "/api/rules",
        json={"name": "Test rule", "rule_type": "unusual_amount", "parameters": {}},
        headers=analyst_headers,
    )
    assert resp.status_code == 403


def test_only_admin_creates_users(client, admin_headers, analyst_headers):
    payload = {
        "username": "newanalyst",
        "email": "new@fraudshield.example",
        "password": "StrongPass123!",
        "role": "analyst",
    }
    assert client.post("/api/auth/users", json=payload, headers=analyst_headers).status_code == 403
    resp = client.post("/api/auth/users", json=payload, headers=admin_headers)
    assert resp.status_code == 201
    # New account can log in
    headers = login(client, "newanalyst", "StrongPass123!")
    assert client.get("/api/auth/me", headers=headers).json()["role"] == "analyst"


def test_audit_log_records_actions(client, admin_headers, analyst_headers):
    client.post("/api/transactions", json=make_txn(transaction_id="TXN-AUDIT-1"),
                headers=analyst_headers)
    resp = client.get("/api/reports/audit-log", headers=admin_headers)
    assert resp.status_code == 200
    actions = [e["action"] for e in resp.json()]
    assert "transaction_ingested" in actions
    assert "login" in actions


def test_viewer_cannot_read_audit_log(client, viewer_headers):
    assert client.get("/api/reports/audit-log", headers=viewer_headers).status_code == 403
