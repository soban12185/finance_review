from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.ai.analyst import run_analyst
from app.core.config import get_settings
from app.core.errors import LLMUnavailable
from app.db.session import get_db
from app.schemas.analyst import AnalystRequest

router = APIRouter()
_settings = get_settings()


@router.post("/chat")
def analyst_chat(body: AnalystRequest, db: Session = Depends(get_db)):
    try:
        response = run_analyst(db, body.question, history=body.history)
    except LLMUnavailable as exc:
        return {
            "answer": "",
            "model": _settings.groq_model,
            "tool_calls": [],
            "error": exc.message,
            "tools_used": [],
            "evidence": {},
            "pipeline": [],
        }
    return {
        "answer": response.answer,
        "model": response.model,
        "tool_calls": [tc.as_dict() for tc in response.tool_calls],
        "error": response.error,
        "stopped_prematurely": response.stopped_prematurely,
        "tools_used": response.tools_used,
        "evidence": response.evidence,
        "pipeline": response.pipeline,
    }


@router.get("/health")
def analyst_health():
    from app.ai.client import get_llm
    from app.core.errors import LLMUnavailable
    try:
        llm = get_llm()
        configured = llm.available()
    except LLMUnavailable:
        configured = False
    return {
        "configured": configured,
        "model": _settings.groq_model,
        "kills": {
            "hint": "Set GROQ_API_KEY to enable AI features. The rest of the app works without it."
        },
    }