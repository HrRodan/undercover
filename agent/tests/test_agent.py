"""Unit tests for the UnderCover Agent and its backend API tools."""

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from agent import main
from backend.main import app


class StubModel(GenericFakeChatModel):
    """A chat model that gives scripted replies in place of a real model."""

    def bind_tools(self, tools: Any, **kwargs: Any) -> "StubModel":
        """Return self when tools are bound."""
        return self


@pytest.fixture
def isolated_backend(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Configure an isolated SQLite database and patch agent.main.backend."""
    monkeypatch.setenv("UNDERCOVER_DB_PATH", str(tmp_path / "agent_test.db"))
    monkeypatch.setattr(main, "backend", lambda: TestClient(app))
    return TestClient(app)


def test_check_backend(isolated_backend: TestClient) -> None:
    """Verify check_backend tool calls /api/health."""
    assert main.check_backend.invoke({}) == "ok"


def test_run_approve_under_limit(isolated_backend: TestClient) -> None:
    """Verify full agent tool loop approves and pays a claim under $1,000."""
    replies = [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "get_claim",
                    "args": {"claim_id": "CLM-1001"},
                    "id": "call-1",
                }
            ],
        ),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "get_policy",
                    "args": {"policy_id": "POL-2001"},
                    "id": "call-2",
                }
            ],
        ),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "get_customer",
                    "args": {"customer_id": "CUS-3001"},
                    "id": "call-3",
                }
            ],
        ),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "get_policy_wording",
                    "args": {},
                    "id": "call-4",
                }
            ],
        ),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "decide_claim",
                    "args": {
                        "claim_id": "CLM-1001",
                        "decision": "approve",
                        "payout": 420.0,
                        "policy_section": "Section 3: Trip Delay",
                        "reason": (
                            "Flight MA 611 was canceled due to crew availability, "
                            "causing a 19-hour delay exceeding the 6-hour Premium "
                            "waiting period. Hotel, meal, and taxi receipts total "
                            "$420.00 within the $800.00 Trip Delay maximum."
                        ),
                    },
                    "id": "call-5",
                }
            ],
        ),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "pay_claim",
                    "args": {"claim_id": "CLM-1001", "amount": 420.0},
                    "id": "call-6",
                }
            ],
        ),
        AIMessage(content="Claim CLM-1001 approved and paid for $420.00."),
    ]
    reply = main.run("CLM-1001", "thread-1", StubModel(messages=iter(replies)))
    assert reply == "Claim CLM-1001 approved and paid for $420.00."

    claim = isolated_backend.get("/api/claims/CLM-1001").json()
    assert claim["status"] == "decided"
    assert claim["decision"] == "approve"
    assert claim["payout"] == 420.0
    assert claim["payment_status"] == "paid"
    assert claim["amount_paid"] == 420.0
    step_messages = [s["message"] for s in claim["steps"]]
    assert step_messages == [
        "Reading claim CLM-1001",
        "Checking policy POL-2001 and plan limits",
        "Reviewing customer claim history for CUS-3001",
        "Reading policy wording",
        "Recording decision: approve ($420.00)",
        "Requesting payout of $420.00",
    ]


def test_run_approve_over_limit_holds_payment_pending_sign_off(
    isolated_backend: TestClient,
) -> None:
    """Verify agent payout over $1,000 is blocked pending handler sign-off."""
    replies = [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "get_claim",
                    "args": {"claim_id": "CLM-1003"},
                    "id": "call-1",
                }
            ],
        ),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "decide_claim",
                    "args": {
                        "claim_id": "CLM-1003",
                        "decision": "approve",
                        "payout": 3750.0,
                        "policy_section": "Section 7: Emergency Medical",
                        "reason": (
                            "Emergency treatment for a fractured wrist in Lisbon is "
                            "covered under Section 7. After the $50.00 Premium "
                            "deductible, the payable amount is $3,750.00."
                        ),
                    },
                    "id": "call-2",
                }
            ],
        ),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "pay_claim",
                    "args": {"claim_id": "CLM-1003", "amount": 3750.0},
                    "id": "call-3",
                }
            ],
        ),
        AIMessage(
            content="Claim CLM-1003 approved for $3,750.00; awaiting handler sign-off."
        ),
    ]
    reply = main.run("CLM-1003", "thread-3", StubModel(messages=iter(replies)))
    assert "awaiting handler sign-off" in reply

    claim = isolated_backend.get("/api/claims/CLM-1003").json()
    assert claim["status"] == "waiting_for_sign_off"
    assert claim["decision"] == "approve"
    assert claim["payout"] == 3750.0
    assert claim["payment_status"] == "pending_sign_off"
    assert claim["amount_paid"] == 0.0
    step_messages = [s["message"] for s in claim["steps"]]
    assert "Payment of $3,750.00 held pending handler sign-off" in step_messages


def test_model_name_and_backend_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify model configuration and default httpx backend client creation."""
    with main.backend() as client:
        assert str(client.base_url).startswith("http://localhost:8000")

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.delenv("MODEL_NAME", raising=False)
    assert main.model().model_name == "openai/gpt-6-luna"
    monkeypatch.setenv("MODEL_NAME", "openrouter/free")
    assert main.model().model_name == "openrouter/free"
