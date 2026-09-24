"""Dataset ingestion endpoints.

* ``POST /api/ingest`` and ``POST /api/ingest/upload`` - multipart file upload
  (.xlsx / .xlsm / .csv), validated and normalized by the shared service.
* ``POST /api/ingest/sample`` - load the bundled sample dataset without any CLI.

Both routes share the same service function and return the same summary shape.
"""
import os

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.core.errors import IngestionError, NotFoundError
from app.core.config import get_settings
from app.db.session import get_db
from app.services.ingestion import IngestionSummary, ingest_file, ingest_workbook

router = APIRouter()

ALLOWED_EXTENSIONS = (".xlsx", ".xlsm", ".csv")
MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB


def _summary_payload(summary: IngestionSummary) -> dict:
    return {
        "filename": summary.filename,
        "status": summary.status,
        "message": summary.message,
        "run_id": summary.run_id,
        # Extended, human-friendly counts.
        "rows_read": summary.rows_read,
        "rows_inserted": summary.rows_inserted if summary.rows_inserted is not None else summary.inserted,
        "rows_duplicate_skipped": (
            summary.rows_duplicate_skipped if summary.rows_duplicate_skipped is not None else summary.duplicates_skipped
        ),
        "rows_failed": summary.rows_failed,
        "review_queue_count": summary.review_queue_count,
        # Original fields, kept for backwards compatibility.
        "total_rows": summary.total_rows,
        "inserted": summary.inserted,
        "duplicates_skipped": summary.duplicates_skipped,
        "errors": summary.errors,
        "potential_duplicates": summary.potential_duplicates,
        "problems": [
            {
                "row_number": p.row_number,
                "transaction_id": p.transaction_id,
                "error_type": p.error_type,
                "message": p.message,
            }
            for p in summary.problems
        ],
    }


def _ingest_upload(file: UploadFile, db: Session) -> dict:
    filename = file.filename or ""
    if not filename.lower().endswith(ALLOWED_EXTENSIONS):
        raise IngestionError("Please upload an .xlsx, .xlsm or .csv file.")
    data = file.file.read()
    if not data:
        raise IngestionError("The uploaded file is empty.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise IngestionError("The uploaded file exceeds the 5 MB upload limit.")
    summary = ingest_workbook(db, filename=filename, data=data)
    return _summary_payload(summary)


def _ingest_sample(db: Session) -> dict:
    settings = get_settings()
    path = settings.sample_dataset_path or settings.seed_dataset_path
    if not path:
        raise IngestionError("The sample dataset is not configured on this server (SAMPLE_DATASET_PATH).")
    if not os.path.exists(path):
        raise NotFoundError(f"Sample dataset not found on server: {path}")
    summary = ingest_file(db, path)
    return _summary_payload(summary)


@router.post("/upload")
def upload_workbook(file: UploadFile = File(...), db: Session = Depends(get_db)):
    return _ingest_upload(file, db)


@router.post("")
def upload_workbook_alias(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Backwards-compatible alias for the original /api/ingest endpoint."""
    return _ingest_upload(file, db)


@router.post("/sample")
def sample_dataset(db: Session = Depends(get_db)):
    return _ingest_sample(db)