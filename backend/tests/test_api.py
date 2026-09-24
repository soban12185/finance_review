"""API endpoint tests via TestClient."""
from tests.conftest import SAMPLE_ROWS, make_workbook_bytes, seed_sample_dataset


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in ("ok", "degraded")


def test_pnl_requires_data_available(client):
    r = client.get("/api/pnl/2026-01")
    assert r.status_code == 200
    lines = r.json()["lines"]
    assert set(lines) == {"revenue", "cogs", "gross_profit", "payroll", "operating_expenses", "operating_profit"}


def test_monthly_pnl_drilldown(client):
    seed_sample_dataset_from_client(client)
    r = client.get("/api/pnl/2026-01/drilldown/revenue")
    assert r.status_code == 200
    body = r.json()
    assert body["computed"] is False
    assert len(body["transactions"]) >= 1
    assert body["transactions"][0]["transaction_id"] == "T5001"

    r2 = client.get("/api/pnl/2026-01/drilldown/gross_profit")
    assert r2.status_code == 200
    assert r2.json()["computed"] is True


def test_list_transactions_filters(client):
    seed_sample_dataset_from_client(client)
    r = client.get("/api/transactions?category=food_sales")
    body = r.json()
    assert body["total"] == 1
    assert body["transactions"][0]["transaction_id"] == "T5001"

    r2 = client.get("/api/transactions?search=sysco")
    assert r2.json()["total"] == 1


def test_transaction_detail(client):
    seed_sample_dataset_from_client(client)
    r = client.get("/api/transactions/T5007")
    assert r.status_code == 200
    assert r.json()["classification"]["category_code"] == "capex_equipment"
    assert r.json()["classification"]["requires_review"] is True


def test_review_workflow_api(client):
    r = seed_sample_dataset_from_client(client)
    items = client.get("/api/reviews?status=pending").json()["items"]
    assert len(items) >= 1
    rv_item = items[0]

    # approve
    res = client.post(f"/api/reviews/{rv_item['id']}/resolve", json={"action": "approve", "note": "ok", "actor": "analyst"})
    assert res.status_code == 200
    assert res.json()["status"] == "approved"


def test_review_change_classification_api(client):
    seed_sample_dataset_from_client(client)
    items = client.get("/api/reviews?status=pending").json()["items"]
    rv_item = items[0]
    res = client.post(
        f"/api/reviews/{rv_item['id']}/resolve",
        json={"action": "change_classification", "category_code": "insurance", "note": "reclass", "actor": "analyst"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "corrected"
    assert body["decided"]["category_code"] == "insurance"


def test_variance_api(client):
    import datetime

    from app.models.transaction import Transaction
    from app.services.classification import build_classification, persist_classification
    from app.financial.money import value_to_cents

    seed_sample_dataset_from_client(client)
    # add a Feb transaction to enable a comparison
    t = Transaction(transaction_id="F0001", date=datetime.date(2026, 2, 10),
                    description="POS batch deposit - food sales week 1", counterparty="Toast POS",
                    amount_cents=value_to_cents("2000.00"), method="Bank deposit")
    with api_session(client) as db:
        db.add(t)
        db.flush()
        data = build_classification(description=t.description, counterparty=t.counterparty,
                                    method=t.method, amount_cents=t.amount_cents)
        persist_classification(db, t, data, actor="system")

    r = client.get("/api/variance?month_a=2026-01&month_b=2026-02")
    assert r.status_code == 200
    lines = {l["line"]: l for l in r.json()["lines"]}
    assert lines["revenue"]["absolute_cents"] == value_to_cents("599.75")


def test_variance_drivers_api(client):
    import datetime

    from app.models.transaction import Transaction
    from app.services.classification import build_classification, persist_classification
    from app.financial.money import value_to_cents

    seed_sample_dataset_from_client(client)
    t = Transaction(transaction_id="F0001", date=datetime.date(2026, 2, 10),
                    description="POS batch deposit - food sales week 1", counterparty="Toast POS",
                    amount_cents=value_to_cents("2000.00"), method="Bank deposit")
    with api_session(client) as db:
        db.add(t)
        db.flush()
        data = build_classification(description=t.description, counterparty=t.counterparty,
                                    method=t.method, amount_cents=t.amount_cents)
        persist_classification(db, t, data, actor="system")

    r = client.get("/api/variance/drivers?month_a=2026-01&month_b=2026-02&line=revenue")
    assert r.status_code == 200
    food = [d for d in r.json()["drivers"] if d["category_code"] == "food_sales"][0]
    assert food["transactions"][0]["transaction_id"] == "F0001"


def test_ingest_api(client):
    r = client.post("/api/ingest", files={
        "file": ("raw.xlsx", make_workbook_bytes(SAMPLE_ROWS), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    })
    assert r.status_code == 200
    assert r.json()["inserted"] == len(SAMPLE_ROWS)


def test_ingest_api_rejects_bad_extension(client):
    r = client.post("/api/ingest", files={"file": ("notes.txt", b"hello", "text/plain")})
    assert r.status_code == 422


def test_categories_api(client):
    r = client.get("/api/categories")
    assert r.status_code == 200
    codes = {c["code"] for c in r.json()}
    assert "food_sales" in codes

    non_pnl = client.get("/api/categories/non-pnl").json()
    assert all(c["accounting_treatment"] in ("capital_expenditure", "sales_tax_liability", "deferred_revenue", "loan_principal", "owner_distribution", "other_non_pnl") for c in non_pnl)


def test_audit_events_api(client):
    seed_sample_dataset_from_client(client)
    r = client.get("/api/reviews/audit/events")
    assert r.status_code == 200
    assert r.json()["total"] >= 1


def test_dashboard_api(client):
    seed_sample_dataset_from_client(client)
    r = client.get("/api/dashboard?month=2026-01")
    assert r.status_code == 200
    body = r.json()
    assert body["selected_month"] == "2026-01"
    assert body["overview"]["lines"]["operating_profit"] is not None
    assert len(body["trend"]) >= 1
    assert body["stats"]["pending_review"] >= 1


def test_analyst_chat_graceful_without_key(client):
    r = client.post("/api/analyst/chat", json={"question": "What was our operating profit in March?", "history": []})
    body = r.json()
    assert body["error"] is not None  # no GROQ_API_KEY in tests
    assert "GROQ_API_KEY" in body["error"]


# ---------------------------------------------------------------------------
def seed_sample_dataset_from_client(client):
    from tests.conftest import seed_sample_dataset
    with api_session(client) as db:
        return seed_sample_dataset(db)


def api_session(client):
    from app.db.session import SessionLocal
    return SessionLocal()