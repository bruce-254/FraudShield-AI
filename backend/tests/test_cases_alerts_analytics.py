"""Case management workflow + alerts + analytics/report endpoints."""
from .conftest import make_txn


def _create_alert(client, analyst_headers, txn_id="TXN-ALERT-1", customer="CUST-A1"):
    client.post("/api/transactions",
                json=make_txn(transaction_id=txn_id, customer_id=customer, amount=80_000),
                headers=analyst_headers)
    alerts = client.get(f"/api/alerts?customer_id={customer}", headers=analyst_headers).json()
    assert alerts, "expected a high-risk alert"
    return alerts[0]


def test_full_case_lifecycle(client, admin_headers, analyst_headers):
    alert = _create_alert(client, analyst_headers)

    # open case with linked alert
    resp = client.post(
        "/api/cases",
        json={
            "title": "Suspicious high-value purchase",
            "description": "Investigating large outlier transaction",
            "customer_id": "CUST-A1",
            "priority": "high",
            "alert_ids": [alert["id"]],
        },
        headers=analyst_headers,
    )
    assert resp.status_code == 201
    case = resp.json()
    assert case["status"] == "open"
    assert len(case["alerts"]) == 1
    assert case["alerts"][0]["status"] == "in_review"

    # assign
    users = client.get("/api/auth/users", headers=admin_headers).json()
    analyst = next(u for u in users if u["username"] == "analyst")
    case = client.patch(f"/api/cases/{case['id']}",
                        json={"assigned_to_id": analyst["id"]},
                        headers=analyst_headers).json()
    assert case["status"] == "assigned"
    assert case["assigned_to"]["username"] == "analyst"

    # investigate + notes
    case = client.patch(f"/api/cases/{case['id']}", json={"status": "investigating"},
                        headers=analyst_headers).json()
    case = client.post(f"/api/cases/{case['id']}/notes",
                       json={"body": "Contacted customer; card reported stolen."},
                       headers=analyst_headers).json()
    assert len(case["notes"]) == 1
    assert case["notes"][0]["author"]["username"] == "analyst"

    # close as confirmed fraud -> linked alert resolves
    case = client.patch(f"/api/cases/{case['id']}",
                        json={"status": "closed_confirmed_fraud"},
                        headers=analyst_headers).json()
    assert case["closed_at"] is not None
    assert case["alerts"][0]["status"] == "resolved"


def test_viewer_cannot_modify_cases(client, analyst_headers, viewer_headers):
    alert = _create_alert(client, analyst_headers, txn_id="TXN-ALERT-2", customer="CUST-A2")
    case = client.post("/api/cases",
                       json={"title": "Test case", "customer_id": "CUST-A2",
                             "alert_ids": [alert["id"]]},
                       headers=analyst_headers).json()
    assert client.patch(f"/api/cases/{case['id']}", json={"status": "investigating"},
                        headers=viewer_headers).status_code == 403
    assert client.post(f"/api/cases/{case['id']}/notes", json={"body": "nope"},
                       headers=viewer_headers).status_code == 403
    # but viewers can read
    assert client.get(f"/api/cases/{case['id']}", headers=viewer_headers).status_code == 200


def test_alert_status_update(client, analyst_headers):
    alert = _create_alert(client, analyst_headers, txn_id="TXN-ALERT-3", customer="CUST-A3")
    resp = client.patch(f"/api/alerts/{alert['id']}/status", json={"status": "dismissed"},
                        headers=analyst_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "dismissed"


def test_analytics_endpoints(client, admin_headers, viewer_headers):
    client.post("/api/admin/seed-synthetic?customers=8&days=10&seed=5", headers=admin_headers)

    summary = client.get("/api/analytics/summary", headers=viewer_headers).json()
    assert summary["total_transactions"] > 0
    assert summary["total_volume"] > 0

    dist = client.get("/api/analytics/risk-distribution", headers=viewer_headers).json()
    assert {d["level"] for d in dist} == {"low", "medium", "high", "critical"}
    assert sum(d["count"] for d in dist) == summary["total_transactions"]

    trend = client.get("/api/analytics/volume-trend?days=30", headers=viewer_headers).json()
    assert len(trend) > 0
    assert all("volume" in p and "count" in p for p in trend)

    top = client.get("/api/analytics/high-risk-customers", headers=viewer_headers).json()
    assert len(top) > 0
    assert top[0]["max_risk"] >= top[-1]["max_risk"]


def test_reports(client, admin_headers, analyst_headers, viewer_headers):
    client.post("/api/admin/seed-synthetic?customers=8&days=10&seed=9", headers=admin_headers)

    report = client.get("/api/reports/fraud-summary?days=60", headers=viewer_headers).json()
    assert report["transactions"] > 0
    assert 0 <= report["flagged_rate"] <= 1

    csv_resp = client.get("/api/reports/transactions.csv?days=60", headers=analyst_headers)
    assert csv_resp.status_code == 200
    lines = csv_resp.text.strip().splitlines()
    assert lines[0].startswith("transaction_id,customer_id")
    assert len(lines) > 1
    # exports are viewer-forbidden (analyst+ only)
    assert client.get("/api/reports/transactions.csv", headers=viewer_headers).status_code == 403


def test_synthetic_data_is_labeled(client, admin_headers, viewer_headers):
    client.post("/api/admin/seed-synthetic?customers=6&days=8&seed=2", headers=admin_headers)
    txns = client.get("/api/transactions?limit=20", headers=viewer_headers).json()
    assert all(t["data_source"] == "synthetic" for t in txns)
    assert all(t["transaction_id"].startswith("SYN-TXN-") for t in txns)
