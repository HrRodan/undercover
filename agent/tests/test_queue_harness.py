"""Unit tests for the Master Queue Agent, subagent delegation, recovery, and CLI."""

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from agent import __main__ as agent_cli
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
    monkeypatch.setenv("UNDERCOVER_DB_PATH", str(tmp_path / "queue_test.db"))
    monkeypatch.setattr(main, "backend", lambda: TestClient(app))
    return TestClient(app)


def test_run_queue_with_cap_todos_and_subagent_delegation(
    isolated_backend: TestClient,
) -> None:
    """Verify queue run plans todos, enforces cap, and delegates 2 claims."""
    queue_replies = [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "get_waiting_claims",
                    "args": {},
                    "id": "q-1",
                }
            ],
        ),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "write_todos",
                    "args": {
                        "todos": [
                            {
                                "claim_id": "CLM-1001",
                                "description": "Trip Delay CLM-1001 ($420)",
                                "status": "in_progress",
                            },
                            {
                                "claim_id": "CLM-1002",
                                "description": "Baggage CLM-1002",
                                "status": "to_do",
                            },
                        ]
                    },
                    "id": "q-2",
                }
            ],
        ),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "work_claim",
                    "args": {"claim_id": "CLM-1001"},
                    "id": "q-3",
                },
            ],
        ),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "work_claim",
                    "args": {"claim_id": "CLM-1002"},
                    "id": "q-4",
                },
                # Also attempt an out-of-cap claim ID to verify cap enforcement
                {
                    "name": "work_claim",
                    "args": {"claim_id": "CLM-1003"},
                    "id": "q-out-of-cap",
                },
            ],
        ),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "check_missed_claims",
                    "args": {},
                    "id": "q-5",
                }
            ],
        ),
        AIMessage(
            content="Worked 2 capped claims: CLM-1001 approved, CLM-1002 declined."
        ),
    ]

    subagent_replies = [
        # Subagent 1: CLM-1001
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
                        "reason": "Covered delay.",
                    },
                    "id": "s1-1",
                },
                {
                    "name": "pay_claim",
                    "args": {"claim_id": "CLM-1001", "amount": 420.0},
                    "id": "s1-2",
                },
            ],
        ),
        AIMessage(content="CLM-1001: approve ($420.00)"),
        # Subagent 2: CLM-1002
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "decide_claim",
                    "args": {
                        "claim_id": "CLM-1002",
                        "decision": "decline",
                        "payout": 0.0,
                        "policy_section": "Section 5: Baggage",
                        "reason": "Excluded.",
                    },
                    "id": "s2-1",
                }
            ],
        ),
        AIMessage(content="CLM-1002: decline ($0.00)"),
    ]

    summary = main.run_queue(
        thread_id="queue-cap-2",
        cap=2,
        llm=StubModel(messages=iter(queue_replies)),
        subagent_llm=StubModel(messages=iter(subagent_replies)),
    )
    assert "Worked 2 capped claims" in summary

    all_claims = isolated_backend.get("/api/claims").json()
    decided = [c for c in all_claims if c["status"] == "decided"]
    waiting = [c for c in all_claims if c["status"] == "waiting"]
    assert len(decided) == 2
    assert len(waiting) == 23

    todos = isolated_backend.get("/api/todos").json()
    assert len(todos) == 2
    assert all(t["status"] == "done" for t in todos)
    assert todos[0]["description"] == "Trip Delay CLM-1001 ($420)"
    assert todos[1]["description"] == "Baggage CLM-1002"

    q_state = isolated_backend.get("/api/queue-run").json()
    assert q_state["status"] == "completed"
    assert q_state["cap"] == 2
    assert "Worked 2 capped claims" in q_state["summary"]


def test_failed_claim_retries_once_and_twice_failed_left_for_handler(
    isolated_backend: TestClient,
) -> None:
    """Verify failed claim retries once and twice-failed claim is left for handler."""
    queue_replies = [
        AIMessage(
            content="",
            tool_calls=[
                {"name": "get_waiting_claims", "args": {}, "id": "q-1"},
                {"name": "work_claim", "args": {"claim_id": "CLM-1001"}, "id": "q-2"},
            ],
        ),
        AIMessage(
            content="",
            tool_calls=[
                {"name": "work_claim", "args": {"claim_id": "CLM-1001"}, "id": "q-3"},
            ],
        ),
        AIMessage(
            content="",
            tool_calls=[
                {"name": "work_claim", "args": {"claim_id": "CLM-1002"}, "id": "q-4"},
            ],
        ),
        AIMessage(
            content="",
            tool_calls=[
                {"name": "work_claim", "args": {"claim_id": "CLM-1002"}, "id": "q-5"},
                {"name": "check_missed_claims", "args": {}, "id": "q-6"},
            ],
        ),
        AIMessage(
            content=(
                "CLM-1001 decided on retry; CLM-1002 left for handler after 2 failures."
            )
        ),
    ]

    subagent_replies = [
        AIMessage(content="I could not decide CLM-1001."),
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
                        "reason": "Covered delay.",
                    },
                    "id": "s-ok-1",
                },
                {
                    "name": "pay_claim",
                    "args": {"claim_id": "CLM-1001", "amount": 420.0},
                    "id": "s-ok-2",
                },
            ],
        ),
        AIMessage(content="CLM-1001: approve ($420.00)"),
        AIMessage(content="Failed attempt 1 on CLM-1002."),
        AIMessage(content="Failed attempt 2 on CLM-1002."),
    ]

    summary = main.run_queue(
        thread_id="queue-failures",
        cap=2,
        llm=StubModel(messages=iter(queue_replies)),
        subagent_llm=StubModel(messages=iter(subagent_replies)),
    )
    assert "CLM-1002 left for handler" in summary

    clm1 = isolated_backend.get("/api/claims/CLM-1001").json()
    assert clm1["status"] == "decided"
    assert clm1["decision"] == "approve"
    assert clm1["attempts"] == 1

    clm2 = isolated_backend.get("/api/claims/CLM-1002").json()
    assert clm2["status"] == "left_for_handler"
    assert clm2["decision"] is None
    assert clm2["attempts"] == 2

    todos = {t["claim_id"]: t for t in isolated_backend.get("/api/todos").json()}
    assert todos["CLM-1001"]["status"] == "done"
    assert todos["CLM-1002"]["status"] == "left_for_handler"


def test_missed_claim_reconciliation_and_cli(
    isolated_backend: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify missed claims within cap are caught and CLI flags work."""
    queue_replies = [
        AIMessage(
            content="",
            tool_calls=[
                {"name": "check_missed_claims", "args": {}, "id": "q-check"},
            ],
        ),
        AIMessage(content="Queue finished."),
    ]
    subagent_replies = [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "decide_claim",
                    "args": {
                        "claim_id": "CLM-1001",
                        "decision": "decline",
                        "payout": 0.0,
                        "policy_section": "Section 3: Trip Delay",
                        "reason": "Declined.",
                    },
                    "id": "s-1",
                }
            ],
        ),
        AIMessage(content="CLM-1001: decline ($0.00)"),
    ]

    main.run_queue(
        thread_id="queue-missed",
        cap=1,
        llm=StubModel(messages=iter(queue_replies)),
        subagent_llm=StubModel(messages=iter(subagent_replies)),
    )
    clm1 = isolated_backend.get("/api/claims/CLM-1001").json()
    assert clm1["status"] == "decided"
    assert clm1["decision"] == "decline"

    monkeypatch.setattr(main, "run", lambda cid, tid: f"Ran {cid}")
    monkeypatch.setattr(main, "run_queue", lambda thread_id, cap: f"Queue cap={cap}")
    assert agent_cli.main_cli(["--claim", "CLM-1001"]) == 0
    assert agent_cli.main_cli(["--cap", "5"]) == 0
