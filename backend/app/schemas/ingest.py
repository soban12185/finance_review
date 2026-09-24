from app.schemas.common import BaseModel, Field


class IngestResponse(BaseModel):
    filename: str
    status: str
    total_rows: int
    inserted: int
    duplicates_skipped: int
    errors: int
    potential_duplicates: int
    run_id: int | None = None
    message: str = ""
    problems: list[dict] = Field(default_factory=list)