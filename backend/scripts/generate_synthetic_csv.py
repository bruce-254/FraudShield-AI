#!/usr/bin/env python3
"""Generate a SYNTHETIC transactions CSV for development/demo.

All data produced is synthetic — no real payment credentials or personal
data. Usage:

    python scripts/generate_synthetic_csv.py out.csv --customers 40 --days 45
"""
import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.synthetic import generate_synthetic_dataset  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", help="output CSV path")
    parser.add_argument("--customers", type=int, default=40)
    parser.add_argument("--days", type=int, default=45)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    rows = generate_synthetic_dataset(args.customers, args.days, seed=args.seed)
    fields = [
        "transaction_id", "customer_id", "timestamp", "amount", "currency",
        "merchant", "location", "channel", "device", "status", "is_fraud_label",
    ]
    with open(args.output, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            row = dict(row)
            row["timestamp"] = row["timestamp"].isoformat()
            writer.writerow(row)
    print(f"Wrote {len(rows)} SYNTHETIC transactions to {args.output}")


if __name__ == "__main__":
    main()
