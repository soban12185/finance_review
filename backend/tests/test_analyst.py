"""Analyst tool-calling loop with a stubbed LLM client."""
import json

import pytest

from app.ai import analyst
from app.ai.analyst import run_analyst


class StubLLM:
    """Simulates Groq chat.completions.create() responses."""
    def __init__(self, script):
        self.script = list(script)
        self.calls = 0

    def chat_completion(self, **kwargs):
        self.calls += 1
        step = self.script[0]
        if len(self.script) > 1:
            self.script.pop(0)
        return step


def _payload_with_tool_calls(answer_then_payload: bool):
    pass


def _tool_payload(name, args, model="test-model"):
    return {
        "model": model,
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {"id": "call_1", "type": "function",
                         "function": {"name": name, "arguments": json.dumps(args)}}
                    ],
                }
            }
        ],
    }


def _final_payload(answer, model="test-model"):
    return {"model": model, "choices": [{"message": {"role": "assistant", "content": answer}}]}


def test_analyst_tool_loop_executes_backend_tool(db_session, monkeypatch):
    from tests.conftest import seed_sample_dataset
    seed_sample_dataset(db_session)

    script = [
        _tool_payload("get_monthly_pnl", {"month": "2026-01"}),
        _final_payload("Operating profit was a loss of $499.75 in January 2026."),
    ]
    stub = StubLLM(script)
    monkeypatch.setattr(analyst, "get_llm", lambda: stub)

    resp = run_analyst(db_session, "What was operating profit in January?")
    assert resp.error is None
    assert "$499.75" in resp.answer or "Operating profit" in resp.answer
    assert len(resp.tool_calls) == 1
    call = resp.tool_calls[0]
    assert call.name == "get_monthly_pnl"
    assert call.result["lines"]["operating_profit"]["amount"] == -499.75


def test_analyst_multi_step_answer_grounded(db_session, monkeypatch):
    from tests.conftest import seed_sample_dataset
    seed_sample_dataset(db_session)

    script = [
        _tool_payload("compare_months", {"month_a": "2026-01", "month_b": "2026-02"}),
        _tool_payload("get_transactions", {"month": "2026-02", "category": "food_inventory"}),
        _final_payload("COGS drivers include food inventory. Evidence: TX5004."),
    ]
    stub = StubLLM(script)
    monkeypatch.setattr(analyst, "get_llm", lambda: stub)

    resp = run_analyst(db_session, "What drove COGS?")
    assert len(resp.tool_calls) == 2
    assert resp.tool_calls[1].name == "get_transactions"
    assert resp.answer


def test_analyst_tool_error_recovered(db_session, monkeypatch):
    from tests.conftest import seed_sample_dataset
    seed_sample_dataset(db_session)

    script = [
        _tool_payload("get_monthly_pnl", {"month": "not-a-month"}),
        _final_payload("That month is invalid; available months are 2026-01."),
    ]
    stub = StubLLM(script)
    monkeypatch.setattr(analyst, "get_llm", lambda: stub)

    resp = run_analyst(db_session, "P&L for not-a-month?")
    # tool error captured, analyst still answered
    assert resp.tool_calls[0].error is not None
    assert resp.answer


def test_analyst_exposes_evidence_and_pipeline(db_session, monkeypatch):
    from tests.conftest import seed_sample_dataset
    seed_sample_dataset(db_session)

    script = [
_tool_payload("compare_months", {"month_a": "2026-01", "month_b": "2026-02"}),
        _tool_payload("get_transactions", {"month": "2026-01", "category": "food_inventory"}),
        _final_payload("COGS drivers include food inventory. Evidence: TX5004."),
    ]
    stub = StubLLM(script)
    monkeypatch.setattr(analyst, "get_llm", lambda: stub)

    resp = run_analyst(db_session, "What drove COGS?")
    # evidence metadata derived only from executed tool results
    assert resp.tools_used == ["compare_months", "get_transactions"]
    assert resp.pipeline == ["deterministic", "retrieval"]
    assert resp.evidence["months"] == ["2026-01", "2026-02"]
    assert resp.evidence["transactions_returned"] > 0
    assert resp.evidence["transaction_ids"]
    assert len(set(resp.evidence["transaction_ids"])) == len(resp.evidence["transaction_ids"])


def test_analyst_no_tool_answer_has_empty_evidence(db_session, monkeypatch):
    stub = StubLLM([_final_payload("No tools were needed.")])
    monkeypatch.setattr(analyst, "get_llm", lambda: stub)

    resp = run_analyst(db_session, "Hi, just a note.")
    assert resp.tool_calls == []
    assert resp.tools_used == []
    assert resp.evidence == {"months": [], "transaction_ids": [], "transactions_returned": 0}
    assert resp.pipeline == []
    from app.core.errors import LLMUnavailable

    def boom():
        raise LLMUnavailable("GROQ_API_KEY is not configured. LLM features are disabled.")

    monkeypatch.setattr(analyst, "get_llm", boom)
    resp = run_analyst(db_session, "What was operating profit?")
    assert resp.error is not None
    assert "GROQ_API_KEY" in resp.error
    assert resp.answer == ""


def test_validation_rejects_short_question(db_session, monkeypatch):
    from app.core.errors import ValidationError
    import pytest as _pytest

    monkeypatch.setattr(analyst, "get_llm", lambda: StubLLM([]))
    with _pytest.raises(ValidationError):
        run_analyst(db_session, "hi")