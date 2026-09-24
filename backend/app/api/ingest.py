from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.core.errors import IngestionError
from app.db.session import get_db
from app.services.ingestion import ingest_workbook

router = APIRouter()


@router.post("")
def upload_workbook(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xlsm")):
        raise IngestionError("Please upload an .xlsx workbook.")
    data = file.file.read()
    if not data:
        raise IngestionError("The uploaded file is empty.")
    summary = ingest_workbook(db, filename=file.filename, data=data)
    return {
        "filename": summary.filename,
        "status": summary.status,
        "total_rows": summary.total_rows,
        "inserted": summary.inserted,
        "duplicates_skipped": summary.duplicates_skipped,
        "errors": summary.errors,
        "potential_duplicates": summary.potential_duplicates,
        "run_id": summary.run_id,
        "message": summary.message,
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