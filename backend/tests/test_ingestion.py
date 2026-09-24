"""Excel ingestion: validation, normalization, dedupe, idempotency."""
import csv
import io

import pytest

from app.core.errors import IngestionError
from app.models.transaction import IngestionRun, Transaction
from app.services.ingestion import ingest_workbook, parse_csv, parse_file, parse_workbook, validate_headers
from tests.conftest import SAMPLE_ROWS, make_workbook_bytes

HEADERS = ["Transaction ID", "Date", "Description", "Counterparty", "Amount", "Method"]


def make_csv_bytes(rows):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(HEADERS)
    w.writerows(rows)
    return buf.getvalue().encode("utf-8")


def test_validate_headers_ok():
    validate_headers(HEADERS)


def test_validate_headers_missing():
    with pytest.raises(IngestionError) as exc:
        validate_headers(["Description", "Amount"])
    assert "missing required columns" in str(exc.value)
    assert "Date" in exc.value.detail["missing_columns"]


def test_parse_workbook_normalizes(db_session):
    rows, problems = parse_workbook(make_workbook_bytes(SAMPLE_ROWS))
    assert len(rows) == len(SAMPLE_ROWS)
    assert not problems
    first = rows[0]
    assert first.transaction_id == "T5001"
    assert first.amount_cents == 120000
    assert first.date.day == 8


def test_parse_workbook_invalid_amount_skipped():
    rows = [SAMPLE_ROWS[0][:], [None] * len(HEADERS), SAMPLE_ROWS[1][:]]
    rows[2][4] = "not-a-number"
    data = make_workbook_bytes(rows)
    parsed, problems = parse_workbook(data)
    assert len(parsed) == 1
    assert problems[0].error_type == "invalid_amount"


def test_parse_workbook_invalid_date_skipped():
    rows = [SAMPLE_ROWS[0][:], SAMPLE_ROWS[1][:]]
    rows[1][1] = "2026-13-45"
    parsed, problems = parse_workbook(make_workbook_bytes(rows))
    assert len(parsed) == 1
    assert problems[0].error_type == "invalid_date"


def test_ingest_inserts_and_classifies(db_session):
    summary = ingest_workbook(db_session, "sample.xlsx", make_workbook_bytes(SAMPLE_ROWS))
    assert summary.inserted == len(SAMPLE_ROWS)
    assert summary.errors == 0
    assert db_session.query(Transaction).count() == len(SAMPLE_ROWS)
    # every inserted transaction must be classified
    from app.models.classification import Classification
    assert db_session.query(Classification).count() == len(SAMPLE_ROWS)


def test_ingest_is_idempotent(db_session):
    data = make_workbook_bytes(SAMPLE_ROWS)
    first = ingest_workbook(db_session, "sample.xlsx", data)
    second = ingest_workbook(db_session, "sample.xlsx", data)
    assert first.inserted == len(SAMPLE_ROWS)
    assert second.inserted == 0
    assert second.duplicates_skipped == len(SAMPLE_ROWS)
    assert db_session.query(Transaction).count() == len(SAMPLE_ROWS)
    # only a single ingestion run is needed per import (2 total here)
    assert db_session.query(IngestionRun).count() == 2


def test_ingest_detects_exact_content_duplicate(db_session):
    data = make_workbook_bytes(SAMPLE_ROWS)
    ingest_workbook(db_session, "sample.xlsx", data)
    # Same content, different transaction id -> potential (exact-content) duplicate
    clone = [[f"T9{t[0][1:]}", t[1], t[2], t[3], t[4], t[5]] for t in SAMPLE_ROWS[:2]]
    summary = ingest_workbook(db_session, "clone.xlsx", make_workbook_bytes(clone))
    assert summary.inserted == 0
    assert summary.potential_duplicates == 2


def test_ingest_preserves_raw_info(db_session):
    ingest_workbook(db_session, "sample.xlsx", make_workbook_bytes(SAMPLE_ROWS))
    txn = db_session.query(Transaction).filter(Transaction.transaction_id == "T5001").one()
    assert txn.raw_amount == "1200.0"
    assert txn.description == "POS batch deposit - food sales week 1"
    assert txn.method == "Bank deposit"


def test_ingest_tracks_errors_in_run(db_session):
    bad = [[h] for h in HEADERS]
    bad = [SAMPLE_ROWS[0][:], ["T9000", "bad-date", "x", "cp", 10, "ACH"]]
    summary = ingest_workbook(db_session, "bad.xlsx", make_workbook_bytes(bad))
    assert summary.inserted == 1
    assert summary.errors == 1


def test_empty_workbook_rejected(db_session):
    import openpyxl

    wb = openpyxl.Workbook()
    # blank worksheet with no header row at all
    buf = io.BytesIO()
    wb.save(buf)
    with pytest.raises(IngestionError):
        parse_workbook(buf.getvalue())


def test_parse_csv_normalizes():
    rows, problems = parse_csv(make_csv_bytes(SAMPLE_ROWS))
    assert len(rows) == len(SAMPLE_ROWS)
    assert not problems
    assert rows[0].transaction_id == "T5001"
    assert rows[0].amount_cents == 120000
    assert rows[0].date.day == 8


def test_parse_csv_captures_row_errors():
    bad = [SAMPLE_ROWS[0][:], SAMPLE_ROWS[1][:]]
    bad[1][1] = "not-a-date"
    rows, problems = parse_csv(make_csv_bytes(bad))
    assert len(rows) == 1
    assert problems[0].error_type == "invalid_date"


def test_parse_file_dispatches_on_extension():
    data = make_csv_bytes(SAMPLE_ROWS)
    rows, problems = parse_file(data, "sample.CSV")
    assert len(rows) == len(SAMPLE_ROWS)
    assert not problems
    with pytest.raises(IngestionError):
        parse_file(b"not a workbook at all", "sample.docx")


def test_ingest_csv_via_filename(db_session):
    summary = ingest_workbook(db_session, "sample.csv", make_csv_bytes(SAMPLE_ROWS))
    assert summary.inserted == len(SAMPLE_ROWS)
    assert db_session.query(Transaction).count() == len(SAMPLE_ROWS)
    from app.models.classification import Classification
    assert db_session.query(Classification).count() == len(SAMPLE_ROWS)


def test_ingest_summary_reports_extended_counts(db_session):
    bad = [SAMPLE_ROWS[0][:], ["T9000", "bad-date", "x", "cp", 10, "ACH"]]
    summary = ingest_workbook(db_session, "mixed.xlsx", make_workbook_bytes(bad))
    assert summary.rows_read == len(bad)
    assert summary.rows_failed == 1
    assert summary.rows_inserted == 1
    assert summary.rows_duplicate_skipped == 0
    assert summary.review_queue_count >= 0
    # duplicate re-import tracks skipped duplicates + zero review traffic
    again = ingest_workbook(db_session, "mixed.xlsx", make_workbook_bytes(bad))
    assert again.rows_inserted == 0
    assert again.rows_duplicate_skipped == 1
    assert again.review_queue_count == 0


def _helper():
    pass