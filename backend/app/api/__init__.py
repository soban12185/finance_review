from fastapi import APIRouter

from app.api import analyst, categories, dashboard, ingest, pnl, reviews, transactions, variance

api_router = APIRouter()
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(transactions.router, prefix="/transactions", tags=["transactions"])
api_router.include_router(categories.router, prefix="/categories", tags=["categories"])
api_router.include_router(reviews.router, prefix="/reviews", tags=["reviews"])
api_router.include_router(pnl.router, prefix="/pnl", tags=["pnl"])
api_router.include_router(variance.router, prefix="/variance", tags=["variance"])
api_router.include_router(ingest.router, prefix="/ingest", tags=["ingest"])
api_router.include_router(analyst.router, prefix="/analyst", tags=["analyst"])