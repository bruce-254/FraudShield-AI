"""ML pipeline tests: real training, honest metrics, graceful failure without
data. Uses the synthetic generator (clearly labeled synthetic data)."""
import pytest

from .conftest import make_txn


def _seed(client, admin_headers, customers=15, days=20):
    resp = client.post(
        f"/api/admin/seed-synthetic?customers={customers}&days={days}&seed=3",
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_training_fails_without_data(client, analyst_headers):
    resp = client.post("/api/ml/train", json={"model_kind": "supervised"}, headers=analyst_headers)
    assert resp.status_code == 400
    assert "labelled" in resp.json()["detail"].lower() or "least" in resp.json()["detail"].lower()

    resp = client.post("/api/ml/train", json={"model_kind": "anomaly"}, headers=analyst_headers)
    assert resp.status_code == 400


def test_supervised_training_produces_real_metrics(client, admin_headers, analyst_headers):
    seeded = _seed(client, admin_headers)
    assert seeded["accepted"] >= 100

    resp = client.post("/api/ml/train", json={"model_kind": "supervised"}, headers=analyst_headers)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    m = body["metrics"]
    for key in ("precision", "recall", "f1", "roc_auc", "confusion_matrix"):
        assert key in m
    assert 0.0 <= m["precision"] <= 1.0
    assert 0.0 <= m["recall"] <= 1.0
    assert 0.0 <= m["f1"] <= 1.0
    assert 0.0 <= m["roc_auc"] <= 1.0
    cm = m["confusion_matrix"]
    assert len(cm) == 2 and len(cm[0]) == 2
    # confusion matrix accounts for exactly the held-out test rows
    assert sum(sum(row) for row in cm) == m["test_size"]
    # the model must genuinely separate classes on synthetic fraud patterns
    assert m["roc_auc"] > 0.6
    assert body["trained_on"] == m["test_size"] + m["train_size"]


def test_anomaly_training_and_scoring(client, admin_headers, analyst_headers):
    _seed(client, admin_headers)
    resp = client.post("/api/ml/train", json={"model_kind": "anomaly"}, headers=analyst_headers)
    assert resp.status_code == 201, resp.text
    assert resp.json()["algorithm"] == "IsolationForest"

    # After training, new transactions include a real anomaly signal.
    txn = client.post(
        "/api/transactions",
        json=make_txn(transaction_id="TXN-ANOM", customer_id="SYN-CUST-0001", amount=45_000),
        headers=analyst_headers,
    ).json()
    signals = txn["risk_factors"]["model_signals"]
    assert signals["anomaly_score"] is not None
    assert 0.0 <= signals["anomaly_score"] <= 1.0


def test_model_signals_absent_until_trained(client, analyst_headers):
    txn = client.post("/api/transactions", json=make_txn(transaction_id="TXN-NOML"),
                      headers=analyst_headers).json()
    signals = txn["risk_factors"]["model_signals"]
    assert signals["supervised_fraud_probability"] is None
    assert signals["anomaly_score"] is None


def test_supervised_model_used_in_scoring_after_training(client, admin_headers, analyst_headers):
    _seed(client, admin_headers)
    client.post("/api/ml/train", json={"model_kind": "supervised"}, headers=analyst_headers)
    txn = client.post(
        "/api/transactions",
        json=make_txn(transaction_id="TXN-MLSCORE", customer_id="SYN-CUST-0000", amount=60),
        headers=analyst_headers,
    ).json()
    proba = txn["risk_factors"]["model_signals"]["supervised_fraud_probability"]
    assert proba is not None and 0.0 <= proba <= 1.0
    component_names = [c["name"] for c in txn["risk_factors"]["components"]]
    assert "supervised_model" in component_names


def test_active_models_endpoint(client, admin_headers, analyst_headers, viewer_headers):
    _seed(client, admin_headers, customers=10, days=15)
    client.post("/api/ml/train", json={"model_kind": "anomaly"}, headers=analyst_headers)
    resp = client.get("/api/ml/models/active", headers=viewer_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["anomaly"] is not None
    assert body["supervised"] is None
