"""FINZ AI-Native Financial Review - FastAPI application."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from app.ai.client import LLMUnavailable as _LLMClientUnavailable  # noqa: F401
from app.api import api_router
from app.core.config import get_settings
from app.core.errors import AppError, DataSourceUnavailable
from app.core.logging import configure_logging, get_logger
from app.db.session import SessionLocal
from app.services.classification import ensure_categories
from app.services.ingestion import ingest_file

logger = get_logger(__name__)
settings = get_settings()
configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting %s v%s", settings.app_name, settings.app_version)
    _bootstrap()
    yield
    logger.info("Shutdown complete")


def _bootstrap() -> None:
    """Idempotent startup bootstrap: catalog sync + optional data seeding.

    All failures are logged and swallowed so the API still boots when the
    database or the seed file is unavailable.
    """
    try:
        with SessionLocal() as db:
            ensure_categories(db)
            logger.info("Category catalog synced.")
            if settings.seed_dataset_path and os.path.exists(settings.seed_dataset_path):
                from app.models.transaction import Transaction
                from sqlalchemy import func
                count = db.query(func.count(Transaction.id)).scalar() or 0
                if count == 0:
                    logger.info("Seeding dataset from %s", settings.seed_dataset_path)
                    summary = ingest_file(db, settings.seed_dataset_path)
                    logger.info("Seed complete: %s", summary.message)
            # Re-run review detection over existing classifications (idempotent):
            # keeps the queue explainable for data classified before this feature.
            from app.services.review_detection import reconcile_pending_reviews
            changed = reconcile_pending_reviews(db)
            if changed:
                logger.info("Review queue reconciled: %s item(s) created/updated.", changed)
    except OperationalError:
        logger.warning("Database not reachable at startup - continuing without bootstrap.")
    except Exception:  # noqa: BLE001 - bootstrap must not kill the process
        logger.exception("Startup bootstrap failed (continuing).")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "AI-native financial review: ingest -> classify -> review -> monthly P&L -> "
        "variance analysis -> grounded AI financial analyst."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message, "detail": exc.detail}},
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "validation_error",
                "message": "Invalid request parameters.",
                "detail": exc.errors(),
            }
        },
    )


@app.exception_handler(OperationalError)
async def db_error_handler(request: Request, exc: OperationalError):
    return JSONResponse(
        status_code=503,
        content={
            "error": {
                "code": "database_unavailable",
                "message": "The database is currently unavailable. Please try again shortly.",
            }
        },
    )


@app.get("/health")
def health():
    db_ok = False
    try:
        with SessionLocal() as db:
            db.execute(__import__("sqlalchemy", fromlist=["text"]).text("SELECT 1"))
        db_ok = True
    except Exception:  # noqa: BLE001
        db_ok = False

    llm_configured = bool(settings.groq_api_key)
    return {
        "status": "ok" if db_ok else "degraded",
        "database": "connected" if db_ok else "unavailable",
        "llm_configured": llm_configured,
        "model": settings.groq_model,
        "version": settings.app_version,
    }


app.include_router(api_router, prefix=settings.api_prefix)