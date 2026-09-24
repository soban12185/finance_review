"""Dataset ingestion service.

Supports the provided ``NYC Restaurant Co. - Raw Transactions.xlsx`` and any
similarly structured workbook. Responsibilities:

* validate required columns and row-level data
* preserve transaction ids and raw values
* normalize dates and amounts (authoritative value stored as integer cents)
* detect duplicate transaction ids and exact-content duplicates
* be idempotent (re-importing the same file never duplicates rows)
* classify every imported transaction via the hybrid classifier
* record a full audit trail of the import
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from io import BytesIO

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.errors import IngestionError
from app.core.logging import get_logger
from app.financial.money import value_to_cents
from app.models.audit_event import AuditEvent
from app.models.transaction import IngestionError as IngestionErrorRow
from app.models.transaction import IngestionRun, Transaction
from app.services.classification import build_classification, ensure_categories, persist_classification

logger = get_logger(__name__)

REQUIRED_COLUMNS = ("Transaction ID", "Date", "Description", "Counterparty", "Amount", "Method")


@dataclass
class RawRow:
    transaction_id: str
    date: date
    description: str
    counterparty: str
    amount_cents: int
    raw_amount: str
    method: str
    row_number: int


@dataclass
class RowProblem:
    row_number: int
    transaction_id: str | None
    error_type: str
    message: str
    row_data: str | None


@dataclass
class IngestionSummary:
    filename: str
    status: str
    total_rows: int
    inserted: int
    duplicates_skipped: int
    errors: int
    potential_duplicates: int
    run_id: int | None = None
    message: str = ""
    problems: list[RowProblem] = field(default_factory=list)


def _raw_amount_str(value: object) -> str:
    """Canonical string form of a numeric amount cell, e.g. 1200 -> '1200.0'."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(float(value))
    return str(value)


def file_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_headers(headers: list[str]) -> None:
    missing = [c for c in REQUIRED_COLUMNS if c not in headers]
    if missing:
        raise IngestionError(
            f"Workbook is missing required columns: {', '.join(missing)}. "
            f"Expected columns: {', '.join(REQUIRED_COLUMNS)}.",
            detail={"missing_columns": missing, "expected": list(REQUIRED_COLUMNS)},
        )


def parse_workbook(data: bytes) -> tuple[list[RawRow], list[RowProblem]]:
    """Parse workbook bytes into normalized rows, collecting per-row problems."""
    try:
        import openpyxl
        wb = openpyxl.load_workbook(BytesIO(data), data_only=True, read_only=True)
    except Exception as exc:  # noqa: BLE001
        raise IngestionError(f"Could not read workbook: {exc}") from exc

    ws = wb.active
    rows_iter = ws.iter_rows(values_only=True)

    try:
        header = next(rows_iter)
    except StopIteration:
        raise IngestionError("Workbook contains no rows.", detail={"expected_columns": list(REQUIRED_COLUMNS)}) from None

    header = [str(h).strip() if h is not None else "" for h in header]
    validate_headers(header)
    col = {name: header.index(name) for name in REQUIRED_COLUMNS}

    rows: list[RawRow] = []
    problems: list[RowProblem] = []

    for idx, raw in enumerate(rows_iter, start=2):
        if raw is None or all(v is None for v in raw):
            continue
        transaction_id = str(raw[col["Transaction ID"]]).strip() if raw[col["Transaction ID"]] is not None else ""

        def problem(error_type: str, message: str) -> None:
            problems.append(RowProblem(
                row_number=idx,
                transaction_id=transaction_id or None,
                error_type=error_type,
                message=message,
                row_data=str(raw),
            ))

        if not transaction_id:
            problem("missing_transaction_id", "Row has no Transaction ID.")
            continue

        date_val = raw[col["Date"]]
        parsed_date: date | None = None
        if isinstance(date_val, datetime):
            parsed_date = date_val.date()
        elif isinstance(date_val, date):
            parsed_date = date_val
        elif isinstance(date_val, str):
            try:  # accept ISO-ish dates
                parsed_date = datetime.strptime(date_val.strip(), "%Y-%m-%d").date()
            except ValueError:
                try:
                    parsed_date = datetime.fromisoformat(date_val.strip()).date()
                except ValueError:
                    parsed_date = None
        if parsed_date is None:
            problem("invalid_date", f"Invalid date value: {date_val!r}")
            continue

        try:
            amount_cents = value_to_cents(raw[col["Amount"]])
        except ValueError as exc:
            problem("invalid_amount", str(exc))
            continue

        description = str(raw[col["Description"]] or "").strip()
        counterparty = str(raw[col["Counterparty"]] or "").strip()
        method = str(raw[col["Method"]] or "").strip()
        raw_amount = _raw_amount_str(raw[col["Amount"]]) if raw[col["Amount"]] is not None else str(amount_cents / 100.0)

        rows.append(RawRow(
            transaction_id=transaction_id,
            date=parsed_date,
            description=description,
            counterparty=counterparty,
            amount_cents=amount_cents,
            raw_amount=raw_amount,
            method=method,
            row_number=idx,
        ))

    return rows, problems


def _classify_and_persist(db: Session, row: RawRow) -> None:
    data = build_classification(
        description=row.description,
        counterparty=row.counterparty,
        method=row.method,
        amount_cents=row.amount_cents,
    )
    txn = Transaction(
        transaction_id=row.transaction_id,
        date=row.date,
        description=row.description,
        counterparty=row.counterparty,
        amount_cents=row.amount_cents,
        method=row.method,
        raw_amount=row.raw_amount,
    )
    db.add(txn)
    db.flush()
    persist_classification(db, txn, data, actor="system")
    db.commit()


def ingest_workbook(db: Session, filename: str, data: bytes) -> IngestionSummary:
    """Ingest workbook bytes. Safe to run multiple times (idempotent)."""
    ensure_categories(db)

    digest = file_hash(data)
    run = IngestionRun(
        filename=filename,
        source_hash=digest,
        status="running",
        total_rows=0,
    )
    db.add(run)
    db.commit()

    rows, problems = parse_workbook(data)
    # Persist parse problems immediately so they are not lost.
    for p in problems:
        _save_row_problem(db, run.id, p)
    run.total_rows = len(rows)

    inserted = 0
    duplicates = 0
    potential = 0

    existing_ids = {
        tid for (tid,) in db.query(Transaction.transaction_id).all()
    }
    # exact-content fingerprint -> transaction id for near-duplicate detection
    existing_fingerprints = _fingerprints(db)

    try:
        for row in rows:
            if row.transaction_id in existing_ids:
                duplicates += 1
                _save_row_problem(db, run.id, RowProblem(
                    row_number=row.row_number,
                    transaction_id=row.transaction_id,
                    error_type="duplicate_transaction_id",
                    message="Transaction ID already exists - skipped (idempotent import).",
                    row_data=row.raw_amount,
                ))
                continue

            fingerprint = _fingerprint(row)
            other = existing_fingerprints.get(fingerprint)
            if other is not None and other != row.transaction_id:
                potential += 1
                _save_row_problem(db, run.id, RowProblem(
                    row_number=row.row_number,
                    transaction_id=row.transaction_id,
                    error_type="potential_duplicate",
                    message=f"Exact content duplicate of {other} (same date/description/counterparty/amount) - skipped.",
                    row_data=None,
                ))
                continue

            try:
                _classify_and_persist(db, row)
                inserted += 1
                existing_ids.add(row.transaction_id)
                existing_fingerprints[fingerprint] = row.transaction_id
            except Exception as exc:  # noqa: BLE001 - row-scoped failure isolation
                logger.exception("Failed to insert row %s", row.transaction_id)
                _save_row_problem(db, run.id, RowProblem(
                    row_number=row.row_number,
                    transaction_id=row.transaction_id,
                    error_type="insert_failed",
                    message=f"Database failure while inserting: {exc}",
                    row_data=None,
                ))
    finally:
        err_count = (
            db.query(func.count(IngestionErrorRow.id))
            .filter(IngestionErrorRow.run_id == run.id).scalar() or 0
        )
        run.status = "completed"
        run.inserted = inserted
        run.duplicates_skipped = duplicates
        run.errors = err_count
        run.potential_duplicates = potential
        run.finished_at = datetime.now(timezone.utc)
        run.message = (
            f"Inserted {inserted} transaction(s), skipped {duplicates} duplicate id(s), "
            f"{potential} exact-content duplicate(s)."
        )
        db.commit()

        db.add(AuditEvent(
            entity_type="ingestion",
            entity_id=str(run.id),
            action="dataset_ingested",
            summary=f"Ingested {filename}: {inserted} new, {duplicates} dup, {potential} near-dup, {err_count} errors.",
            new_value={
                "filename": filename,
                "source_hash": digest,
                "inserted": inserted,
                "duplicates_skipped": duplicates,
                "errors": err_count,
                "potential_duplicates": potential,
            },
            actor="system",
        ))
        db.commit()

    summary = IngestionSummary(
        filename=filename,
        status="completed",
        total_rows=len(rows),
        inserted=inserted,
        duplicates_skipped=duplicates,
        errors=run.errors,
        potential_duplicates=potential,
        run_id=run.id,
        message=run.message,
        problems=problems,
    )
    return summary


def _save_row_problem(db: Session, run_id: int, p: RowProblem) -> None:
    db.add(IngestionErrorRow(
        run_id=run_id,
        row_number=p.row_number,
        transaction_id=p.transaction_id,
        error_type=p.error_type,
        message=p.message,
        row_data=p.row_data,
    ))
    db.commit()


def _fingerprint(row: RawRow) -> str:
    return f"{row.date.isoformat()}|{row.description.strip().lower()}|{row.counterparty.strip().lower()}|{row.amount_cents}"


def _fingerprints(db: Session) -> dict[str, str]:
    out: dict[str, str] = {}
    for tid, d, desc, cp, amt in db.query(
        Transaction.transaction_id,
        Transaction.date,
        Transaction.description,
        Transaction.counterparty,
        Transaction.amount_cents,
    ).all():
        fp = f"{d.isoformat()}|{desc.strip().lower()}|{cp.strip().lower()}|{amt}"
        out[fp] = tid
    return out


def ingest_file(db: Session, filename: str) -> IngestionSummary:
    """Read a workbook from disk and ingest it (used by CLI scripts)."""
    with open(filename, "rb") as fh:
        data = fh.read()
    return ingest_workbook(db, filename, data)