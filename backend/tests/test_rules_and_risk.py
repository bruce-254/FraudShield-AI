"""Rule engine + risk scoring tests: rules come from the DB, are configurable,
and produce explainable scores/alerts."""
from datetime import datetime, timedelta

from .conftest import make_txn


def test_default_rules_seeded(client, viewer_headers):
    resp = client.get("/api/rules", headers=viewer_headers)
    assert resp.status_code == 200
    types = {r["rule_type"] for r in resp.json()}
    assert types == {
        "unusual_amount", "rapid_frequency", "geo_anomaly",
        "repeated_failures", "behavior_change",
    }


def test_unusual_amount_triggers_alert(client, analyst_headers):
    resp = client.post(
        "/api/transactions",
        json=make_txn(transaction_id="TXN-BIG", amount=50_000),
        headers=analyst_headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    hit_types = [h["rule_type"] for h in body["risk_factors"]["rule_hits"]]
    assert "unusual_amount" in hit_types
    assert body["risk_score"] >= 60

    alerts = client.get("/api/alerts", headers=analyst_headers).json()
    assert any(a["transaction"]["transaction_id"] == "TXN-BIG" for a in alerts)


def test_rapid_frequency_rule(client, analyst_headers):
    base = datetime.utcnow()
    for i in range(7):
        client.post(
            "/api/transactions",
            json=make_txn(
                transaction_id=f"TXN-FAST-{i}",
                customer_id="CUST-FAST",
                timestamp=(base - timedelta(minutes=30) + timedelta(minutes=4 * i)).isoformat(),
                amount=30,
            ),
            headers=analyst_headers,
        )
    last = client.get("/api/transactions/TXN-FAST-6", headers=analyst_headers).json()
    hit_types = [h["rule_type"] for h in last["risk_factors"]["rule_hits"]]
    assert "rapid_frequency" in hit_types


def test_repeated_failures_rule(client, analyst_headers):
    base = datetime.utcnow()
    for i in range(4):
        client.post(
            "/api/transactions",
            json=make_txn(
                transaction_id=f"TXN-FAIL-{i}",
                customer_id="CUST-FAILER",
                timestamp=(base - timedelta(hours=5) + timedelta(hours=i)).isoformat(),
                status="failed",
            ),
            headers=analyst_headers,
        )
    resp = client.post(
        "/api/transactions",
        json=make_txn(
            transaction_id="TXN-FAIL-FINAL",
            customer_id="CUST-FAILER",
            timestamp=base.isoformat(),
        ),
        headers=analyst_headers,
    )
    hit_types = [h["rule_type"] for h in resp.json()["risk_factors"]["rule_hits"]]
    assert "repeated_failures" in hit_types


def test_rule_configuration_changes_behavior(client, admin_headers, analyst_headers):
    """Tightening the DB-stored threshold changes scoring – proof rules are
    data-driven, not hardcoded."""
    rules = client.get("/api/rules", headers=admin_headers).json()
    ua = next(r for r in rules if r["rule_type"] == "unusual_amount")

    # 500 is below default absolute_threshold -> no hit
    r1 = client.post("/api/transactions",
                     json=make_txn(transaction_id="TXN-CFG-1", amount=500),
                     headers=analyst_headers).json()
    assert "unusual_amount" not in [h["rule_type"] for h in r1["risk_factors"]["rule_hits"]]

    # Tighten threshold via API
    resp = client.patch(
        f"/api/rules/{ua['id']}",
        json={"parameters": {**ua["parameters"], "absolute_threshold": 400}},
        headers=admin_headers,
    )
    assert resp.status_code == 200

    r2 = client.post("/api/transactions",
                     json=make_txn(transaction_id="TXN-CFG-2", amount=500,
                                   customer_id="CUST-CFG2"),
                     headers=analyst_headers).json()
    assert "unusual_amount" in [h["rule_type"] for h in r2["risk_factors"]["rule_hits"]]


def test_disabled_rule_not_evaluated(client, admin_headers, analyst_headers):
    rules = client.get("/api/rules", headers=admin_headers).json()
    ua = next(r for r in rules if r["rule_type"] == "unusual_amount")
    client.patch(f"/api/rules/{ua['id']}", json={"enabled": False}, headers=admin_headers)

    resp = client.post("/api/transactions",
                       json=make_txn(transaction_id="TXN-DIS", amount=99_999),
                       headers=analyst_headers).json()
    assert "unusual_amount" not in [h["rule_type"] for h in resp["risk_factors"]["rule_hits"]]


def test_risk_score_is_explainable(client, analyst_headers):
    resp = client.post("/api/transactions",
                       json=make_txn(transaction_id="TXN-EXPL", amount=25_000),
                       headers=analyst_headers).json()
    factors = resp["risk_factors"]
    assert "components" in factors and len(factors["components"]) >= 1
    total_contribution = sum(c["contribution"] for c in factors["components"])
    assert abs(total_contribution - resp["risk_score"]) < 1.0
    assert "behavioral_context" in factors
    for hit in factors["rule_hits"]:
        assert hit["detail"]  # every hit carries a human-readable explanation


def test_score_preview_does_not_persist(client, analyst_headers):
    resp = client.post("/api/transactions/score-preview",
                       json=make_txn(transaction_id="TXN-PREVIEW", amount=70_000),
                       headers=analyst_headers)
    assert resp.status_code == 200
    assert resp.json()["score"] >= 0
    assert client.get("/api/transactions/TXN-PREVIEW", headers=analyst_headers).status_code == 404
