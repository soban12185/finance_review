from app.schemas.common import BaseModel, Field


class AnalystRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    history: list[dict] = Field(default_factory=list, max_length=20)


class ToolCallOut(BaseModel):
    id: str
    name: str
    arguments: dict
    result: dict | None = None
    error: str | None = None


class AnalystResponseOut(BaseModel):
    answer: str
    model: str
    tool_calls: list[ToolCallOut] = []
    error: str | None = None
    stopped_prematurely: bool = False
    tools_used: list[str] = []
    evidence: dict = {}
    pipeline: list[str] = []