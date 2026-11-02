# AuditProcurement

# AuditAI

> **AI-powered financial fraud detection system for enterprise audit teams.**

AuditAI is a full-stack financial anomaly detection platform built for audit firms, banks, and large corporates. It combines OCR receipt parsing, a two-stage ML pipeline (PyTorch Autoencoder + Scikit-learn Isolation Forest), SHAP explainability, and Gemini-powered audit report generation into a single, demoable v1.

---

## 🚀 Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | FastAPI (Python) |
| **Frontend** | React + Vite |
| **Database** | PostgreSQL |
| **ML** | PyTorch (Autoencoder), Scikit-learn (Isolation Forest), SHAP |
| **OCR** | PaddleOCR (primary), Pytesseract (fallback) |
| **LLM** | Google Gemini API |

---

## 🧠 What It Detects (v1: Employee Expense Fraud)

- **Typosquatting vendors** (e.g. "Zomto Food" vs "Zomato")
- **Duplicate claims** (fuzzy-matched by vendor + amount + date)
- **Amount inflation** (OCR receipt vs. claimed amount mismatch)
- **Split transactions** (multiple claims on same date from same employee)
- **Weekend/holiday claims**
- **Round-number anomalies**
- **Related-party transactions**
- **Benford's Law deviations**
- **Segregation of Duties violations**

---

## 📐 ML Architecture

```
Raw Expense Claims
      ↓
Feature Engineering (15 features per claim)
      ↓
Stage 1: PyTorch Autoencoder → Reconstruction Error
      ↓
Stage 2: Isolation Forest (on reconstructed features) → Anomaly Score
      ↓
Combined Score = 0.4 × Recon Error + 0.6 × IF Score
      ↓
SHAP Explainability → Gemini Audit Report Generation
```

---

## 🏗️ Project Structure

```
AuditAI/
├── backend/
│   └── app/
│       ├── api/           # FastAPI routers (claims, fraud, cases, analytics, reports)
│       ├── models/        # SQLAlchemy ORM models
│       ├── schemas/       # Pydantic request/response schemas
│       ├── features/      # Feature engineering (15 fraud signals)
│       ├── ml/            # Autoencoder, Isolation Forest, SHAP pipeline
│       ├── ocr/           # PaddleOCR + Tesseract dual-engine
│       ├── llm/           # Gemini API integration
│       └── config.py      # Centralized hyperparameters
├── frontend/
│   └── src/
│       ├── pages/         # Dashboard, Upload, ClaimsTable, ClaimDetail, AuditScreens
│       ├── components/    # Navbar, StatCard, ScoreBadge, ShapChart, ScoreGauge, etc.
│       └── api/           # Axios API client
├── scripts/
│   ├── generate_expense_claims.py   # Synthetic data generator
│   └── seed_and_train.py            # One-command pipeline setup
└── data/                            # Generated CSVs and synthetic receipts
```

---

## ⚡ Quick Start

### 1. Prerequisites
- Python 3.10+
- Node.js 18+
- Docker Desktop (recommended for the local PostgreSQL database)

### 2. Start PostgreSQL

Copy the safe template, choose a local development password, then start the
database container. The `.env` file is ignored by Git and must never be
committed.

```bash
cp .env.example .env
docker compose up -d postgres
```

Check that PostgreSQL is healthy:

```bash
docker compose ps
python scripts/check_database.py
```

### 3. Install backend dependencies
```bash
pip install fastapi uvicorn sqlalchemy psycopg2-binary pandas numpy torch scikit-learn shap fuzzywuzzy python-Levenshtein python-multipart google-generativeai pillow opencv-python-headless
```

### 4. Start the backend
```bash
python -m uvicorn backend.app.main:app --reload --port 8000
```

### 5. Seed the database + train models
```bash
python scripts/seed_and_train.py
```

### 6. Start the frontend
```bash
cd frontend && npm install && npm run dev
```

Open **http://localhost:5173** to see the dashboard.

---

## 📊 Dashboard Features

- **Audit Dashboard** — KPI metrics, monthly flagged claims bar chart, score distribution
- **High-Risk Claims Queue** — Filter by case status, risk level, and keyword search
- **Inline Typosquat Warnings** — Hover tooltips showing `⚠ 89% match to 'Domino's Pizza'`
- **3-Tier Risk Colors** — Amber (50-70%), Orange (70-85%), Red (85%+)
- **Claim Detail** — OCR results, SHAP waterfall chart, score gauges, AI audit report
- **Maker-Checker Workflow** — Makers recommend, Checkers sign off, append-only trail
- **Audit Screens** — Benford's Law chart, Related-Party screening, SoD violations

---

## 🔑 Key API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/claims/upload` | Upload CSV of expense claims |
| `GET` | `/api/v1/claims` | List claims with filters and pagination |
| `POST` | `/api/v1/fraud/train` | Train ML pipeline |
| `POST` | `/api/v1/fraud/score` | Score all claims |
| `GET` | `/api/v1/fraud/summary` | Dashboard statistics |
| `GET` | `/api/v1/analytics/benford` | Benford's Law distribution |
| `GET` | `/api/v1/analytics/related-parties` | Related-party screen |
| `GET` | `/api/v1/analytics/sod-violations` | SoD violations |
| `POST` | `/api/v1/cases/{id}/maker-recommend` | Maker recommendation |
| `POST` | `/api/v1/cases/{id}/checker-signoff` | Checker final sign-off |

---

## 📄 License

MIT

## Procurement workspace

AuditAI now opens into a Zip-inspired procurement workspace. The original expense
analytics, claims, ingestion, control points and audit screens remain available in
the sidebar. Purchase requests are a separate domain from employee expenses.

Implemented flow:

1. Request wizard: business purpose, department, category, USD line items, supplier
   and payment-recipient references, spending limit, payment terms and documents.
2. Optional quote prefill through Gemini. Extracted fields remain editable and
   require review; missing supplier/recipient identifiers are not invented.
3. Sequential manager and finance approvals; personal-data sharing adds security
   review. A requester cannot approve their own request. Request-more-information,
   resubmission and rejection are supported.
4. Approved PO snapshots are created only after the required approvals finish.
5. Invoice checks compare SKU, description, quantities, prices, delivery, tax,
   supplier, recipient, arithmetic and total. One invoice per PO is supported.
6. A discrepancy creates an exception. A correction request can be generated and
   recorded internally; corrected invoices preserve every submitted version.
7. Autoencoder-decoded output feeds Isolation Forest. Anomaly assessments augment
   exact rules; they do not establish fraud or override mismatches.
8. An independent finance reviewer records a reason before sandbox checkout.
9. Optional PayPal sandbox order creation, payer approval, capture and explicit
   status reconciliation. Provider totals, currency, recipient and invoice binding
   are verified. Stable persisted idempotency keys protect retries.
10. Role-scoped records, supporting document downloads, comments and audit events.

### Start locally

From the repository root, with the configured PostgreSQL database available:

```bash
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m scripts.init_procurement
.venv/bin/python -m scripts.train_procurement_model
.venv/bin/python -m uvicorn backend.app.main:app --reload --port 8000
```

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

The frontend uses same-origin `/api/v1`. The Vite dev proxy forwards API calls
to `http://127.0.0.1:8000`; set `API_PROXY_TARGET` to change that destination.
Alternatively set `VITE_API_BASE_URL` for a separate API origin and include the
frontend origin in `CORS_ORIGINS`. The proxy also keeps local OTP cookies on the
same browser origin.

The table initializer is additive and does not change or drop existing tables.
It also creates missing authentication tables. It now includes workflow,
activity, documents, invoice revisions and payment-attempt tables. An Alembic
migration history has not yet replaced this initializer.

### Demo accounts and roles

Optional local-only seed (fictional records, no external payments):

```bash
.venv/bin/python -m scripts.seed_procurement_demo
```

Sign in using `demo.auditor@example.com`, `demo.manager@example.com`,
`demo.finance@example.com`, or `demo.security@example.com`. Local development OTPs
are displayed when `AUTH_DEBUG_OTP=true`; otherwise configure delivery normally.
The demo recipient is deliberately unconfigured and cannot be paid.

For an existing account, a local operator can assign a role explicitly:

```bash
.venv/bin/python -m scripts.set_procurement_role --email manager@example.com --role manager
```

Role assignment is not exposed through a public self-service API. The app models
one company; it is not a multi-tenant deployment.

### Trained procurement model

The supplied training script produces
`backend/trained_models/procurement_bundle.joblib` and
`backend/trained_models/procurement_evaluation.json`. The bundle includes the
scaler, AE parameters, Isolation Forest, ordered feature schema, fixed validation
reference distributions, threshold and synthetic-data provenance.

Architecture: eight procurement features -> autoencoder (latent dimension 3) ->
decoded feature vector -> Isolation Forest. The final review score combines
40% AE reconstruction-error percentile and 60% decoded-space IF percentile.
Normalization is fixed to validation references, not the current invoice batch.

Training uses 6,000 normal synthetic feature records; validation uses 1,500 normal
records; testing uses 1,500 normal and 500 injected-anomaly records, with separate
random seeds. The initial run achieved approximately 83.4% precision, 45.2% recall
and 3.0% false-positive rate on that synthetic test set. These are simulator
results, not real-world fraud accuracy. All invoices still require independent
finance review. Unknown suppliers and cold-start histories can be flagged.

This procurement bundle does not replace the original expense model artifacts.
Set `PROCUREMENT_MODEL_BUNDLE` to use a compatible trusted procurement bundle.
Do not load arbitrary untrusted joblib/pickle files. Model binaries are ignored
by Git; reproduce them with the training command when cloning the project.

### Optional service configuration

- `GEMINI_API_KEY` and `GEMINI_MODEL`: quote extraction (new `google-genai` SDK).
  PDFs are limited to 20 pages and uploads to 10 MB. Uploading a quote for prefill
  sends its contents to Gemini after the user selects Extract quote fields.
- `PAYPAL_SANDBOX_CLIENT_ID`, `PAYPAL_SANDBOX_CLIENT_SECRET`, and
  `PAYPAL_SANDBOX_MERCHANT_ID`: sandbox checkout only. The approved recipient must
  match the configured merchant. No live PayPal endpoint is supported.
- PayPal status is reconciled by an explicit provider-status request and before
  capture; webhook processing and scheduled reconciliation are not implemented.

### Scope and limitations

Supplier directory entries are references derived from requests, not verified
supplier identities. Spending limits apply per request; shared budget reservation,
multi-entity VAT, ERP/Jira/Slack integrations, legal review and electronic signature
are not implemented. Payment terms are recorded but scheduled settlement is not
implemented. Agent-to-agent price negotiation and external supplier messaging are
also not implemented; the correction coordinator records a local action instead.
The audit trail records application events; it is not an immutable external ledger.

### Verify

```bash
.venv/bin/python -m pytest tests -q
cd frontend
npm run build
npm run lint
```

The procurement suite verifies approvals, self-approval prevention, scoped access,
extra charges, invoice corrections/version history, document access, deterministic
model inference and mocked PayPal replay/amount/recipient controls. Real PayPal
and Gemini calls require configured credentials and separate integration testing.
