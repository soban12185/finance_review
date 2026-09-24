"""Test fixtures.

Tests run against an in-memory SQLite database (deterministic), while the
production application uses PostgreSQL via DATABASE_URL. The financial layer is
dialect-agnostic, so engine behaviour is identical on both.
"""
from __future__ import annotations

import os

os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ["ENABLE_LLM_CLASSIFICATION"] = "false"
os.environ["GROQ_API_KEY"] = ""

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, event  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

import app.models  # noqa: E402 F401
from app.core.config import get_settings  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.services.classification import ensure_categories  # noqa: E402


@pytest.fixture()
def settings():
    return get_settings()


@pytest.fixture()
def db_engine():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture()
def db_session(db_engine):
    factory = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)
    db = factory()
    ensure_categories(db)
    yield db
    db.close()


@pytest.fixture()
def client(db_engine, db_session, monkeypatch):
    import app.db.session as db_module
    from app.main import app

    factory = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)
    monkeypatch.setattr(db_module, "SessionLocal", factory)
    monkeypatch.setattr(db_module, "engine", db_engine)
    with TestClient(app) as c:
        yield c


def make_workbook_bytes(rows, headers=None) -> bytes:
    """Build an in-memory xlsx for ingestion tests."""
    import io

    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(headers or ["Transaction ID", "Date", "Description", "Counterparty", "Amount", "Method"])
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


SAMPLE_ROWS = [
    ["T5001", "2026-01-08", "POS batch deposit - food sales week 1", "Toast POS", 1200.00, "Bank deposit"],
    ["T5002", "2026-01-09", "POS batch deposit - beverage sales week 1", "Toast POS", 300.50, "Bank deposit"],
    ["T5003", "2026-01-10", "Refunds and discounts week 1", "Toast POS", -100.25, "POS adjustment"],
    ["T5004", "2026-01-11", "Food inventory purchase - Sysco", "Sysco", -400.00, "ACH/card"],
    ["T5005", "2026-01-12", "Payroll - hourly kitchen and FOH wages", "Gusto Payroll", -500.00, "ACH"],
    ["T5006", "2026-01-13", "Rent", "Landlord", -1000.00, "ACH"],
    ["T5007", "2026-01-14", "Equipment purchase - new oven", "Restaurant Equipment World", -5000.00, "ACH"],
]


def seed_sample_dataset(db) -> int:
    """Insert the sample rows + classifications; returns number inserted."""
    from app.models.transaction import Transaction
    from app.services.ingestion import ingest_workbook

    summary = ingest_workbook(db, "sample.xlsx", make_workbook_bytes(SAMPLE_ROWS))
    return summary.inserted