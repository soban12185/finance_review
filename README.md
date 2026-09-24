# FINZ · AI-Native Financial Review

A full-stack financial review application built to demonstrate AI-native
engineering: ingest a raw transactions workbook, classify it with a hybrid
deterministic-first pipeline (LLM assist only where rules are unclear), review
flagged items, and explore the resulting P&L, variance and AI analyst answers —
where the AI must show the tools it ran, the months it used and the transaction
ids that back every claim.

The backend is FastAPI + PostgreSQL (SQLAlchemy 2 / Alembic, integer-cents
arithmetic only — never floats). The frontend is React + Vite + TypeScript +
Tailwind. The AI layer uses Groq for classification assistance and the AI
Analyst, but **every financial number is computed in the backend**; the LLM can
only read controlled tool results and phrase answers.

---

## AI-Native Engineering

This project is deliberately engineered so that **AI adds reasoning, never
authority over numbers**. The same principles show up in the code, the UI and
the tests:

### Where AI is used
- **Classification assist** (Groq, structured JSON) — only when deterministic
  rules are unclear (`LLM_CLASSIFICATION_THRESHOLD`, default 0.80).
- **AI Financial Analyst** — selects read-only tools, and writes the final
  answer. It retrieves rows via validated SQL tool functions and reads
  engine-computed totals; it never calculates or invents figures.
- Every screen that touches AI shows its source: `Rule` / `AI` / `Manual`
  badges, confidence %, and review flags.

### Where the deterministic engine is the source of truth
- All amounts are stored as integer cents (`amount_cents`, BIGINT). P&L,
  net cash, gross/operating profit, variance, materiality and driver
  attribution are pure Python arithmetic — deterministic on every run,
  auditable transaction by transaction. The LLM never touches these numbers.
- The engine is expressed in code (`app/financial/`) and labelled in the UI
  ("Integer-cent engine", "Deterministic engine", "Deterministic calculation").

### How incorrect answers are prevented
- **Grounding rules** in the analyst system prompt: never invent transactions,
  totals, categories, percentages or transaction ids; never compute
  authoritative totals independently; always call a tool before quoting a
  number; reproduce exact tool values; explicitly flag insufficient evidence;
  separate facts (tool output) from interpretation; no chain-of-thought.
- **Read-only tool surface.** The model has no database access — every request
  goes through validated, schema-bound functions in `app/ai/tools.py`
  (`get_monthly_pnl`, `compare_months`, `get_transactions`, …), with strict
  argument validation and error recovery.
- **Hybrid classification.** Manual corrections are authoritative; automated
  classifications never overwrite them.
- **No RAG, by design.** Data is fully structured in PostgreSQL, so answers are
  produced by deterministic SQL retrieval + engine math rather than semantic
  search over embeddings. Qdrant/Pinecone/FAISS/Chroma are intentionally not
  used; see "How It Works" in the app.

### How outputs are verified
- **Review Queue** surfaces low-confidence, judgment-heavy, unusual and
  inconsistent items with the *reasons* they were flagged; approve / reclassify
  / mark non-P&L decisions are recorded in `audit_event`.
- **Drill-downs** — every P&L line decomposes into its exact transactions.
- **Variance drivers** — each driver references the transactions behind it.
- **Analyst evidence.** Every answer returns `tool_calls`, `tools_used`,
  `pipeline` (retrieval → deterministic calc → evidence → explanation) and an
  `evidence` block listing the months analyzed and the real transaction ids
  returned by the tools. Evidence is collected *only* from tool output actually
  retrieved in that conversation — never inferred or fabricated. The analyst
  page displays these as the "Evidence used" panel.

---

## Architecture

```
Raw Transactions.xlsx (181 rows, Jan–Mar 2026)
        │  ingestion (validate → normalize → dedupe → classify)
        ▼
   PostgreSQL ── transaction, classification,
   (single DB)     classification_history, review_item, audit_event,
                   category, ingestion_run, ingestion_error
        │
        ├── Deterministic financial engine (monthly P&L, integer cents)
        ├── Variance analysis (materiality thresholds, driver attribution)
        └── AI Analyst (Groq tool-calling loop over read-only tools)
        │
        ▼
   REST API (FastAPI, /api/*) → React SPA
```

### Key decisions

- **Integer cents are authoritative.** Amounts are stored as `BIGINT`
  (`amount_cents`). Every engine calculation is integer arithmetic; money is
  only converted to dollars for display via a single `cents_to_amount` helper.
- **Hybrid classification pipeline.** Deterministic rules run first. If rule
  confidence is below `LLM_CLASSIFICATION_THRESHOLD` (default 0.80), the LLM is
  asked (Groq, structured JSON) on the backend only. Manual corrections are
  authoritative — automated classifications never overwrite them.
- **Review queue.** Classifications with `confidence < 0.92` or on non-P&L items
  (capex, sales-tax remittance, gift-card deposits, loan principal, owner
  distributions) create review items — as do unusual amounts and
  description/rule inconsistencies. Every item explains *why* it was flagged
  (sources + reasons) and carries a suggested action. Approve / reclassify /
  mark non-P&L actions are recorded with full audit history.
- **AI Analyst safety.** The analyst answers from backend tool results
  (`get_monthly_pnl`, `compare_months`, `get_variance_drivers`,
  `get_transactions`, …). It has no database access, cannot modify records, and
  is instructed never to invent figures. When `GROQ_API_KEY` is absent the app
  still works end to end (rules + review queue); the analyst reports the missing
  key instead of erroring.

---

## Quick start (Docker)

```bash
# 1. Provide your Groq key (optional but recommended)
copy .env.example .env      # then edit GROQ_API_KEY=

# 2. Build and start everything (PostgreSQL + backend + frontend)
docker compose up --build -d

# 3. Open the app
#    http://localhost:5173
#    API docs: http://localhost:8000/docs
#    Health:    http://localhost:8000/health
```

The dataset lives in `data\` and is mounted read-only into the backend, ready
to be ingested from the UI, the script, or the API:

```bash
docker compose exec backend sh -c \
  'python scripts/ingest_dataset.py "/data/NYC Restaurant Co. - Raw Transactions.xlsx"'
```

No CLI needed: the **Dashboard has an "Import dataset" card** — drag & drop or
pick an `.xlsx` / `.xlsm` / `.csv` file (max 5 MB), or click **"Load sample
dataset"** to pull the bundled workbook from the server. Both routes return the
same summary (rows read / inserted / duplicates / failed, row-level problems,
and how many items were sent to the review queue).

API endpoints:

* `POST /api/ingest/upload` — multipart upload (also at legacy `POST /api/ingest`).
* `POST /api/ingest/sample` — load the sample dataset configured via
  `SEED_DATASET_PATH` / `SAMPLE_DATASET_PATH` (in docker compose:
  `/app/sample_data/NYC Restaurant Co. - Raw Transactions.xlsx`, baked into the
  image; on Render/cloud: `sample_data/...` next to `requirements.txt`).

## Deploy to production (free tier: Render + Vercel + Neon)

The repo ships the pieces needed for a free cloud deployment:

* `backend/sample_data/` — the sample workbook is **baked into the repo**, so
  "Load sample dataset" and first-boot seeding work on any host with no volumes.
* `render.yaml` — Render Blueprint that provisions the free backend service.
* `frontend/vercel.json` — SPA rewrites so deep links work on Vercel's free tier.

Steps:

1. **Database (Neon, free forever)** — create a project at
   https://neon.tech/projects, copy the connection string
   (`postgresql://user:pass@ep-…neon.tech/db?sslmode=require`). No need to
   change the scheme — the app normalises `postgresql://` to the psycopg driver
   automatically.
2. **Backend (Render)** — push this repo to GitHub, then
   *New + → Blueprint* on https://render.com, pick the repo, and click
   *Apply*. Enter the **Neon DB URL** for `DATABASE_URL` and (optional) your
   `GROQ_API_KEY`. The service auto-runs migrations (`alembic upgrade head`),
   seeds the sample data on an empty database, and exposes `/health`.
3. **Frontend (Vercel)** — in https://vercel.com/new import the same repo;
   **Root Directory: `frontend`**, framework auto-detected as Vite. Add an
   environment variable (**Production + Preview**):
   `VITE_API_BASE = https://<your-backend>.onrender.com`, then Deploy.
4. **Check** — open the Vercel URL, hit **Load sample dataset**, and confirm
   the Dashboard/P&L/review queue populate.

Free-tier caveats: Render's free web service sleeps after ~15 minutes idle and
cold-starts in ~50 s on the next request; Neon free plans cap at 0.5 GB storage.
`CORS_ORIGINS` is set to `*` in `render.yaml` for the demo — tighten it to your
exact Vercel origin by replacing `*` with your app URL.

## Local development (no Docker for the app code)

Requires Python 3.11+ and Node 20+. PostgreSQL can run via
`docker compose up -d db`.

```bash
# Backend
cd backend
python -m venv .venv && .venv\Scripts\activate     # Windows
pip install -r requirements.txt
copy .env.example .env
$env:DATABASE_URL="postgresql+psycopg://finz:finz@localhost:5432/finz"
alembic upgrade head
python scripts/ingest_dataset.py "..\data\NYC Restaurant Co. - Raw Transactions.xlsx"
uvicorn app.main:app --reload

# Frontend (separate terminal)
cd frontend
npm install
npm run dev          # http://localhost:5173 (proxies /api to :8000)
```

## Guided demo (11 steps)

1. **Import** — on the Dashboard, use the "Import dataset" card: drop a
   workbook, or click **"Load sample dataset"** for the bundled data. See rows
   read / inserted / duplicates / failed, any row-level problems, and how many
   items were flagged for review — all without touching a terminal.
2. **Dashboard** — see the "AI-Native Financial Review" explainer: AI-Powered /
   Deterministic Engine / Human-in-the-loop, plus the pipeline strip.
3. **How It Works** — open the architecture page: 8-step processing pipeline
   with deterministic/AI/human badges, the four pillars (AI · Deterministic ·
   Retrieval · Human), where AI is used vs not, and why there is no vector RAG.
4. **Transactions** — filter the 181 classified rows and check the source badge
   (Rule / AI / Manual), confidence % and review flags on each row.
5. **Review Queue** — open any pending item: you'll see *why* it was flagged
   (review sources + reasons) and the system's suggested action. Approve,
   reclassify or mark non-P&L.
6. **P&L** — click a line to drill down to the exact transactions; computed
   lines are marked; the page declares the integer-cent engine.
7. **Variance** — compare two months, expand a material line, and inspect the
   traceable driver transactions.
8. **AI Analyst** — ask "Why did operating profit change between February and
   March?". Watch the pipeline strip (tool selection → SQL retrieval /
   deterministic calculation → evidence → explanation).
9. **Evidence panel** — the analyst's answer cites tool names, months and
   transaction ids; click any id to jump to that transaction. Evidence is only
   ever what the tools actually returned.
10. **Determinism check** — re-run a P&L or variance calculation: identical
    numbers every time. The LLM only rewords explanations, never the totals.
11. **Tests** — run `pytest` (below): the suite locks in the grounding rules,
    evidence collection, review triggers and deterministic engine, so an
    AI-native regression fails the build.

## Tests

```bash
cd backend
.\.venv\Scripts\python -m pytest -q        # 122 tests, in-memory SQLite, no network
```

## Dataset

`data\NYC Restaurant Co. - Raw Transactions.xlsx` — 181 unique transactions for
Jan–Mar 2026 with fields `Transaction ID, Date, Description, Counterparty,
Amount, Method`. Patterns cover revenue (POS food/beverage, catering, delivery
payouts), contra-revenue (refunds, discounts, delivery commissions), COGS,
payroll, operating expenses, and non-P&L items (capex, sales-tax remittances,
gift-card deposits, loan principal, owner distributions) that must be reviewed.

## Project layout

```
backend/
  app/
    main.py                # FastAPI app, lifespan, CORS, error mapping
    api/                   # transactions, categories, reviews, pnl, variance,
                           # ingest, analyst, dashboard routers
    classification/        # category catalog + deterministic rules
    services/              # classification, ingestion, review workflows
    financial/             # money, engine (P&L), variance
    ai/                    # Groq client, classifier, tools, analyst tool loop
    models/  schemas/  repositories/  core/  db/
  alembic/                 # initial schema + category seed migration
  scripts/                 # ingest_dataset.py, summary.py
  tests/                   # 122 tests incl. API-level integration
frontend/
  src/pages/               # Dashboard, Transactions, Review Queue, P&L,
                           # Variance, AI Analyst, How It Works (architecture)
  src/components/          # Card, ImportCard (upload + sample dataset), ui
  src/lib/
docker-compose.yml         # db + backend + frontend
```