"""Ingestion + validation tests."""
import io
from datetime import datetime, timedelta

from .conftest import make_txn


def test_ingest_valid_transaction(client, analyst_headers):
    resp = client.post("/api/transactions", json=make_txn(), headers=analyst_headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["risk_score"] is not None
    assert body["risk_level"] in ("low", "medium", "high", "critical")
    assert "components" in body["risk_factors"]


def test_duplicate_transaction_rejected(client, analyst_headers):
    txn = make_txn(transaction_id="TXN-DUP")
    assert client.post("/api/transactions", json=txn, headers=analyst_headers).status_code == 201
    assert client.post("/api/transactions", json=txn, headers=analyst_headers).status_code == 409


def test_validation_rejects_bad_input(client, analyst_headers):
    bad_amount = make_txn(amount=-5)
    assert client.post("/api/transactions", json=bad_amount, headers=analyst_headers).status_code == 422

    bad_currency = make_txn(transaction_id="TXN-X1", currency="usd$")
    assert client.post("/api/transactions", json=bad_currency, headers=analyst_headers).status_code == 422

    bad_channel = make_txn(transaction_id="TXN-X2", channel="carrier_pigeon")
    assert client.post("/api/transactions", json=bad_channel, headers=analyst_headers).status_code == 422

    injection_id = make_txn(transaction_id="TXN'; DROP TABLE--")
    assert client.post("/api/transactions", json=injection_id, headers=analyst_headers).status_code == 422

    far_future = make_txn(
        transaction_id="TXN-X3",
        timestamp=(datetime.utcnow() + timedelta(days=10)).isoformat(),
    )
    assert client.post("/api/transactions", json=far_future, headers=analyst_headers).status_code == 422


def test_batch_csv_ingestion(client, analyst_headers):
    now = datetime.utcnow()
    lines = ["transaction_id,customer_id,timestamp,amount,currency,merchant,location,channel,device,status"]
    for i in range(5):
        lines.append(
            f"CSV-{i},CUST-CSV,{(now - timedelta(hours=i)).isoformat()},"
            f"{20 + i},USD,GrocerMart,London-GB,online,web-chrome,approved"
        )
    lines.append("CSV-BAD,CUST-CSV,not-a-date,xx,USD,Shop,London-GB,online,web,approved")
    content = "\n".join(lines).encode()

    resp = client.post(
        "/api/transactions/batch",
        files={"file": ("batch.csv", io.BytesIO(content), "text/csv")},
        headers=analyst_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["accepted"] == 5
    assert body["rejected"] == 1
    assert len(body["errors"]) == 1


def test_list_and_filter_transactions(client, analyst_headers, viewer_headers):
    for i in range(3):
        client.post("/api/transactions", json=make_txn(transaction_id=f"TXN-L{i}"),
                    headers=analyst_headers)
    resp = client.get("/api/transactions?customer_id=CUST-001", headers=viewer_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 3
