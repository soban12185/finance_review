"""Ingest the FINZ dataset (or any compatible workbook) into the database.

Usage from backend/:
    python scripts/ingest_dataset.py "data/NYC Restaurant Co. - Raw Transactions.xlsx"
    # or with DATABASE_URL exported:
    python scripts/ingest_dataset.py
    # without arguments it uses the default dataset path when available.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.logging import configure_logging, get_logger  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.services.ingestion import ingest_file  # noqa: E402

logger = get_logger("ingest_dataset")

DEFAULT_DATASETS = [
    "data/NYC Restaurant Co. - Raw Transactions.xlsx",
    "../data/NYC Restaurant Co. - Raw Transactions.xlsx",
]


def main() -> None:
    configure_logging()
    parser = argparse.ArgumentParser(description="Ingest a financial transactions workbook (Excel).")
    parser.add_argument("dataset", nargs="?", help="Path to the .xlsx workbook.")
    parser.add_argument("--drop-first", action="store_true", help="(optional) dangerous - not implemented.")
    args = parser.parse_args()

    path = args.dataset
    if not path:
        for candidate in DEFAULT_DATASETS:
            if os.path.exists(candidate):
                path = candidate
                break
    if not path or not os.path.exists(path):
        logger.error("Dataset not found. Pass a path to an .xlsx file.")
        sys.exit(2)

    with SessionLocal() as db:
        summary = ingest_file(db, path)
    print("=" * 60)
    print(f"File                 : {Path(path).name}")
    print(f"Status               : {summary.status}")
    print(f"Rows                 : {summary.total_rows}")
    print(f"Inserted             : {summary.inserted}")
    print(f"Duplicate IDs skipped: {summary.duplicates_skipped}")
    print(f"Exact-content dups   : {summary.potential_duplicates}")
    print(f"Errors               : {summary.errors}")
    print(f"Message              : {summary.message}")
    if summary.problems:
        print("-" * 60)
        for p in summary.problems[:20]:
            print(f"  row {p.row_number} ({p.error_type}): {p.message}")
        if len(summary.problems) > 20:
            print(f"  ... and {len(summary.problems) - 20} more.")
    print("=" * 60)


if __name__ == "__main__":
    main()