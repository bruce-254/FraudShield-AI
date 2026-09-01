# 🛡 FraudShield AI

A **defensive** financial fraud detection and transaction analytics platform. FraudShield AI monitors transaction streams, flags suspicious patterns with a configurable rule engine plus real machine learning, produces **explainable risk scores**, and gives analysts a full alerting, case-management and reporting workflow.

> **Privacy & safety:** This project is for defensive fraud monitoring only. All development data is **synthetic** and clearly labeled as such (`data_source="synthetic"`, `SYN-*` identifiers). No real payment credentials or personal data are used anywhere. ML metrics are always computed on genuine held-out evaluation data — there are no fake results or hardcoded predictions.

## Architecture

```
React + TypeScript (Vite)  ──►  FastAPI (Python)  ──►  PostgreSQL
        dashboard                REST API + JWT          (SQLite fallback for dev/tests)
                                     │
                     pandas / numpy feature engineering
                     rule engine (rules stored in DB)
                     scikit-learn (RandomForest + IsolationForest)
```

| Layer | Tech |
|---|---|
| API | FastAPI, SQLAlchemy 2, Pydantic v2 |
| Data science | pandas, NumPy, scikit-learn, joblib |
| Database | PostgreSQL (production), SQLite (dev/CI) |
| Frontend | React 19, TypeScript, Vite, Recharts |
| Auth | JWT (OAuth2 password flow), bcrypt, RBAC |
| DevOps | Docker, docker-compose, GitHub Actions |

## Features

- **Transaction ingestion** — single JSON or batch CSV upload; strict Pydantic validation (amount bounds, ISO currency, ID character allow-lists, timestamp sanity).
- **Feature engineering** — per-customer behavioural features (amount z-score vs. own history, velocity counts, failed-attempt counts, location/device novelty, time-of-day) computed with pandas/NumPy.
- **Rule engine** — rules are **database records**, not code: each row selects a rule *type* (evaluator) and carries its own JSON parameters, severity and enabled flag. Ships with five defaults: unusual amount, rapid frequency, geographic anomaly, repeated failures, sudden behavioral change. Tune/disable/add via API or UI — no redeploys.
- **ML classification** — RandomForest trained on labeled data with train/test split; reports **precision, recall, F1, ROC-AUC and confusion matrix** from the held-out set only.
- **Anomaly detection** — IsolationForest for the unlabeled case, with percentile-calibrated 0–1 scores; honestly evaluated against labels when labels happen to exist.
- **Explainable risk scoring** — 0–100 score blending rule hits, supervised fraud probability and anomaly score with configurable weights. Every score ships its factor breakdown: per-component contributions, triggered rules with human-readable reasons, model signals and behavioural context.
- **Alerts** — automatically raised when the score crosses the threshold; triage workflow (review / escalate / dismiss / resolve).
- **Case management** — open cases from alerts, assign analysts, track status through investigation, add notes, close with a disposition (confirmed fraud / false positive / inconclusive). Closing a case auto-resolves linked alerts.
- **Analytics dashboard** — volumes, trends, risk distribution, high-risk customers, alert/case status.
- **Reports** — fraud summary per period, CSV export, full audit trail.
- **Security** — JWT auth, RBAC (`admin` / `analyst` / `viewer`), audit logging of every sensitive action, input validation everywhere, no secrets in code.

## Quick start (Docker)

```bash
cp .env.example .env          # set FRAUDSHIELD_SECRET_KEY
docker compose up --build
# open http://localhost:8080
```

## Quick start (local dev)

```bash
# backend (uses SQLite automatically if FRAUDSHIELD_DATABASE_URL is unset)
cd backend
pip install -r requirements.txt -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000

# frontend
cd frontend
npm install
npm run dev                   # proxies /api → localhost:8000
```

Development bootstrap accounts (change in production):

| Username | Password | Role |
|---|---|---|
| `admin` | `AdminPass123!` | admin |
| `analyst` | `AnalystPass123!` | analyst |
| `viewer` | `ViewerPass123!` | viewer |

### Demo flow

1. Sign in as `admin`, go to **ML Models** → *Seed synthetic data* (generates labeled synthetic customers with injected fraud archetypes: amount spikes, velocity bursts, geo-hopping, failed-attempt probing, account takeover).
2. Train the **supervised classifier** and the **anomaly detector** — real metrics appear.
3. Explore the **Dashboard**, drill into flagged **Transactions**/**Alerts** to see explainable score factors.
4. Open a **Case** from an alert, assign it, add notes, close it.
5. Check **Reports** for the fraud summary, CSV export and audit log.

## API

Interactive docs at `http://localhost:8000/docs`. Key endpoints:

| Method | Path | Role | Purpose |
|---|---|---|---|
| POST | `/api/auth/login` | – | JWT login |
| POST | `/api/transactions` | analyst | ingest + score one transaction |
| POST | `/api/transactions/batch` | analyst | CSV batch ingest |
| POST | `/api/transactions/score-preview` | analyst | what-if scoring (not persisted) |
| GET/POST/PATCH/DELETE | `/api/rules` | admin (write) | manage DB-stored rules |
| GET/PATCH | `/api/alerts` | analyst (write) | alert triage |
| POST/PATCH | `/api/cases`, `/api/cases/{id}/notes` | analyst | case workflow |
| POST | `/api/ml/train` | analyst | train supervised/anomaly model |
| GET | `/api/analytics/*` | viewer | dashboard aggregates |
| GET | `/api/reports/*` | viewer/analyst | reports, CSV export, audit log |
| POST | `/api/admin/seed-synthetic` | admin | seed synthetic dev data |

## Testing

```bash
cd backend && pytest tests -q      # 33 tests: auth/RBAC, validation, rules, ML, cases, analytics
```

CI (GitHub Actions) runs backend tests, frontend type-check/build and Docker image builds on every push.

## Repository layout

```
backend/
  app/
    main.py            # app factory, bootstrap
    config.py          # env-driven settings
    models.py          # SQLAlchemy models
    schemas.py         # Pydantic validation
    core/security.py   # JWT, bcrypt, RBAC
    services/          # features, rule_engine, ml, risk, ingestion, synthetic, audit
    routers/           # auth, transactions, rules, alerts, cases, ml, analytics, reports, admin
  tests/               # pytest suite
  scripts/             # synthetic CSV generator
frontend/              # React + TS dashboard (Vite)
docker-compose.yml     # PostgreSQL + backend + nginx frontend
.github/workflows/     # CI
```
