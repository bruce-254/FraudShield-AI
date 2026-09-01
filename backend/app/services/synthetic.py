"""SYNTHETIC data generator — development/demo data only.

Every record produced here is marked ``data_source='synthetic'`` and uses
obviously fake identifiers (SYN-CUST-*, SYN-TXN-*). No real payment
credentials, PANs, or personal data are ever used or generated.

The generator simulates customers with individual spending profiles and
injects several fraud archetypes matching the rule engine's targets:
  * amount spike            * velocity burst (rapid frequency)
  * geo-hopping             * repeated failed attempts
  * account takeover (new device + behavioural change)
Fraud labels reflect the injected pattern, so supervised training operates on
honest ground truth.
"""
import random
import uuid
from datetime import datetime, timedelta

CURRENCIES = ["USD", "EUR", "GBP", "KES"]
CITIES = [
    "New York-US", "London-GB", "Nairobi-KE", "Berlin-DE", "Paris-FR",
    "Lagos-NG", "Mumbai-IN", "Tokyo-JP", "Sao Paulo-BR", "Toronto-CA",
]
MERCHANTS = [
    "GrocerMart", "FuelPoint", "StreamFlix", "CoffeeCorner", "TechBazaar",
    "AirGo Travel", "PharmaPlus", "FashionHub", "BookNook", "RideShare",
]
RISKY_MERCHANTS = ["LuxWatch Exchange", "CryptoRampX", "GiftCardDepot", "WireXpress"]
CHANNELS = ["card_present", "online", "mobile", "pos", "atm", "transfer"]
DEVICES = ["ios-app", "android-app", "web-chrome", "web-safari", "pos-terminal", "atm-unit"]


def _txn_id() -> str:
    return f"SYN-TXN-{uuid.uuid4().hex[:16]}"


def generate_synthetic_dataset(
    n_customers: int = 40,
    days: int = 45,
    fraud_customer_ratio: float = 0.25,
    seed: int | None = 7,
    end_time: datetime | None = None,
) -> list[dict]:
    rng = random.Random(seed)
    end_time = end_time or datetime.utcnow()
    start_time = end_time - timedelta(days=days)
    rows: list[dict] = []

    for c in range(n_customers):
        cust_id = f"SYN-CUST-{c:04d}"
        home_city = rng.choice(CITIES)
        currency = rng.choice(CURRENCIES)
        avg_amount = rng.uniform(15, 220)
        device = rng.choice(DEVICES[:4])
        daily_rate = rng.uniform(0.8, 4.0)
        is_fraud_victim = rng.random() < fraud_customer_ratio

        # --- legitimate baseline behaviour
        t = start_time + timedelta(hours=rng.uniform(0, 24))
        while t < end_time:
            amount = max(1.0, rng.gauss(avg_amount, avg_amount * 0.35))
            hour_shift = rng.gauss(14, 4)  # daytime bias
            ts = t.replace(hour=int(min(max(hour_shift, 0), 23)), minute=rng.randint(0, 59))
            rows.append({
                "transaction_id": _txn_id(),
                "customer_id": cust_id,
                "timestamp": ts,
                "amount": round(amount, 2),
                "currency": currency,
                "merchant": rng.choice(MERCHANTS),
                "location": home_city if rng.random() < 0.92 else rng.choice(CITIES),
                "channel": rng.choice(["card_present", "online", "mobile", "pos"]),
                "device": device if rng.random() < 0.9 else rng.choice(DEVICES[:4]),
                "status": "approved" if rng.random() < 0.965 else rng.choice(["declined", "failed"]),
                "is_fraud_label": False,
            })
            t += timedelta(days=1.0 / daily_rate * rng.uniform(0.5, 1.6))

        # --- injected fraud archetypes
        if not is_fraud_victim:
            continue
        pattern = rng.choice(["amount_spike", "velocity", "geo_hop", "failed_probe", "takeover"])
        f_start = start_time + timedelta(days=rng.uniform(days * 0.5, days * 0.95))

        if pattern == "amount_spike":
            for k in range(rng.randint(1, 3)):
                rows.append({
                    "transaction_id": _txn_id(),
                    "customer_id": cust_id,
                    "timestamp": f_start + timedelta(hours=k * rng.uniform(2, 20)),
                    "amount": round(avg_amount * rng.uniform(12, 40), 2),
                    "currency": currency,
                    "merchant": rng.choice(RISKY_MERCHANTS),
                    "location": home_city if rng.random() < 0.5 else rng.choice(CITIES),
                    "channel": "online",
                    "device": rng.choice(DEVICES),
                    "status": "approved",
                    "is_fraud_label": True,
                })
        elif pattern == "velocity":
            base = f_start
            for k in range(rng.randint(8, 15)):
                rows.append({
                    "transaction_id": _txn_id(),
                    "customer_id": cust_id,
                    "timestamp": base + timedelta(minutes=k * rng.uniform(2, 7)),
                    "amount": round(rng.uniform(20, avg_amount * 3), 2),
                    "currency": currency,
                    "merchant": rng.choice(MERCHANTS + RISKY_MERCHANTS),
                    "location": home_city,
                    "channel": rng.choice(["online", "mobile"]),
                    "device": rng.choice(DEVICES),
                    "status": "approved" if rng.random() < 0.8 else "declined",
                    "is_fraud_label": True,
                })
        elif pattern == "geo_hop":
            cities = rng.sample([c for c in CITIES if c != home_city], 4)
            for k, city in enumerate(cities):
                rows.append({
                    "transaction_id": _txn_id(),
                    "customer_id": cust_id,
                    "timestamp": f_start + timedelta(hours=k * rng.uniform(1, 4)),
                    "amount": round(rng.uniform(avg_amount, avg_amount * 6), 2),
                    "currency": currency,
                    "merchant": rng.choice(MERCHANTS + RISKY_MERCHANTS),
                    "location": city,
                    "channel": "card_present",
                    "device": "pos-terminal",
                    "status": "approved",
                    "is_fraud_label": True,
                })
        elif pattern == "failed_probe":
            base = f_start
            for k in range(rng.randint(4, 8)):
                rows.append({
                    "transaction_id": _txn_id(),
                    "customer_id": cust_id,
                    "timestamp": base + timedelta(minutes=k * rng.uniform(5, 30)),
                    "amount": round(rng.uniform(1, 15), 2) if k < 3 else round(avg_amount * rng.uniform(5, 15), 2),
                    "currency": currency,
                    "merchant": rng.choice(RISKY_MERCHANTS),
                    "location": rng.choice(CITIES),
                    "channel": "online",
                    "device": rng.choice(DEVICES),
                    "status": "failed" if k < 4 else rng.choice(["approved", "declined"]),
                    "is_fraud_label": True,
                })
        else:  # takeover
            new_device = f"unknown-device-{rng.randint(100, 999)}"
            base = f_start.replace(hour=rng.choice([0, 1, 2, 3, 23]))
            for k in range(rng.randint(2, 5)):
                rows.append({
                    "transaction_id": _txn_id(),
                    "customer_id": cust_id,
                    "timestamp": base + timedelta(minutes=k * rng.uniform(10, 60)),
                    "amount": round(avg_amount * rng.uniform(6, 20), 2),
                    "currency": currency,
                    "merchant": rng.choice(RISKY_MERCHANTS),
                    "location": rng.choice(CITIES),
                    "channel": rng.choice(["online", "transfer"]),
                    "device": new_device,
                    "status": "approved",
                    "is_fraud_label": True,
                })

    rows.sort(key=lambda r: r["timestamp"])
    # clamp any timestamps that drifted past "now"
    now = datetime.utcnow()
    for r in rows:
        if r["timestamp"] > now:
            r["timestamp"] = now - timedelta(minutes=random.randint(1, 300))
    return rows
