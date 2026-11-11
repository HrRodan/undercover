"""Unit tests for the UnderCover Claim Subagent, tools, middleware, and config."""

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, ToolMessage

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


def test_run_approve_under_limit_and_read_sections(
    isolated_backend: TestClient,
) -> None:
    """Verify subagent reads sections, approves, and pays a claim under $1,000."""
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
                    "name": "list_document_sections",
                    "args": {"doc_name": "policy_wording"},
                    "id": "call-4a",
                },
                {
                    "name": "search_documents",
                    "args": {"query": "Trip Delay waiting period"},
                    "id": "call-4b",
                },
                {
                    "name": "read_document_section",
                    "args": {
                        "doc_name": "policy_wording",
                        "section_id": "Trip Delay",
                    },
                    "id": "call-4c",
                },
                {
                    "name": "read_document_section",
                    "args": {
                        "doc_name": "claims_manual",
                        "section_id": "7",
                    },
                    "id": "call-4d",
                },
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
        AIMessage(content="CLM-1001: approve ($420.00)"),
    ]
    reply = main.run("CLM-1001", "thread-1", StubModel(messages=iter(replies)))
    assert reply == "CLM-1001: approve ($420.00)"

    claim = isolated_backend.get("/api/claims/CLM-1001").json()
    assert claim["status"] == "decided"
    assert claim["decision"] == "approve"
    assert claim["payout"] == 420.0
    assert claim["payment_status"] == "paid"
    assert claim["amount_paid"] == 420.0
    assert "Policy Wording — Trip Delay" in claim["sections_read"]
    assert "Claims Manual — 7. Interpretation notes" in claim["sections_read"]


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


def test_model_configuration_and_reasoning_efforts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify queue (medium) and claim (low) model configurations and overrides."""
    with main.backend() as client:
        assert str(client.base_url).startswith("http://localhost:8000")

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.delenv("MODEL_NAME", raising=False)
    monkeypatch.delenv("QUEUE_MODEL_NAME", raising=False)
    monkeypatch.delenv("CLAIM_MODEL_NAME", raising=False)
    monkeypatch.delenv("QUEUE_REASONING_EFFORT", raising=False)
    monkeypatch.delenv("CLAIM_REASONING_EFFORT", raising=False)

    q_model = main.model("queue")
    c_model = main.model("claim")
    assert q_model.model_name == "openai/gpt-6-luna"
    assert q_model.reasoning_effort == "medium"
    assert c_model.model_name == "openai/gpt-6-luna"
    assert c_model.reasoning_effort == "low"

    monkeypatch.setenv("MODEL_NAME", "openrouter/free")
    assert main.model("queue").model_name == "openrouter/free"
    assert main.model("queue").reasoning_effort is None
    assert main.model("claim").model_name == "openrouter/free"
    assert main.model("claim").reasoning_effort is None

    monkeypatch.setenv("QUEUE_REASONING_EFFORT", "high")
    assert main.model("queue").reasoning_effort == "high"
    monkeypatch.setenv("QUEUE_REASONING_EFFORT", "none")
    assert main.model("queue").reasoning_effort is None


def test_tools_recover_from_wrong_id_and_prevent_double_decision(
    isolated_backend: TestClient,
) -> None:
    """Verify tool error recovery on 404 and duplicate decision/pay guards."""
    assert "error" in main.get_policy.invoke({"policy_id": "CLM-1001"})
    assert "error" in main.get_customer.invoke({"customer_id": "CLM-1001"})
    assert "error" in main.list_document_sections.invoke({"doc_name": "invalid"})[0]
    assert "error" in main.read_document_section.invoke(
        {"doc_name": "claims_manual", "section_id": "999"}
    )
    assert "version" in main.get_policy_wording.invoke({})

    dec = main.decide_claim.invoke(
        {
            "claim_id": "CLM-1001",
            "decision": "Approved",
            "payout": 420.0,
            "policy_section": "Section 3: Trip Delay",
            "reason": "Covered delay.",
        }
    )
    assert dec["decision"] == "approve"
    assert dec["status"] == "decided"

    dup_dec = main.decide_claim.invoke(
        {
            "claim_id": "CLM-1001",
            "decision": "decline",
            "payout": 0.0,
            "policy_section": "Section 3: Trip Delay",
            "reason": "Duplicate.",
        }
    )
    assert dup_dec["status"] == "already_decided"

    paid = main.pay_claim.invoke({"claim_id": "CLM-1001", "amount": 420.0})
    assert paid["payment_status"] == "paid"

    dup_paid = main.pay_claim.invoke({"claim_id": "CLM-1001", "amount": 420.0})
    assert dup_paid["status"] == "conflict"


def test_middleware_model_retry_and_tool_error_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify model_retry_middleware and tool_error_boundary_middleware."""
    monkeypatch.setenv("MODEL_MAX_RETRIES", "3")
    attempts = 0

    def flaky_handler(_req: Any) -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 2:
            raise RuntimeError("Transient OpenRouter 502")
        return "recovered"

    res = main.model_retry_middleware.wrap_model_call(None, flaky_handler)  # type: ignore[arg-type]
    assert res == "recovered"
    assert attempts == 2

    def always_failing_handler(_req: Any) -> str:
        raise RuntimeError("Permanent failure")

    with pytest.raises(RuntimeError, match="Permanent failure"):
        main.model_retry_middleware.wrap_model_call(None, always_failing_handler)  # type: ignore[arg-type]

    class DummyToolReq:
        tool_call = {"name": "get_claim", "id": "tc-99"}

    def failing_tool_handler(_req: Any) -> ToolMessage:
        raise ValueError("Bad tool input")

    err_msg = main.tool_error_boundary_middleware.wrap_tool_call(
        DummyToolReq(),  # type: ignore[arg-type]
        failing_tool_handler,
    )
    assert isinstance(err_msg, ToolMessage)
    assert "Error in get_claim: Bad tool input" in str(err_msg.content)
