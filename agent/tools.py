"""Tools, middleware, and HTTP client helpers for the UnderCover Agent Harness."""

import sys
from collections.abc import Callable
from contextvars import ContextVar
from typing import Any

import httpx
from langchain.agents.middleware import (
    ModelCallResult,
    ModelRequest,
    ToolCallRequest,
    wrap_model_call,
    wrap_tool_call,
)
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langgraph.types import Command

from agent.config import get_agent_config

HTTP_CONFLICT = 409
MAX_ATTEMPTS_BEFORE_HANDLER = 2

_DECISION_ALIASES: dict[str, str] = {
    "approve": "approve",
    "approved": "approve",
    "decline": "decline",
    "declined": "decline",
    "refer": "refer",
    "referred": "refer",
}

_TODO_STATUS_ALIASES: dict[str, str] = {
    "to_do": "to_do",
    "todo": "to_do",
    "pending": "to_do",
    "waiting": "to_do",
    "in_progress": "in_progress",
    "working": "in_progress",
    "done": "done",
    "completed": "done",
    "complete": "done",
    "decided": "done",
    "left_for_handler": "left_for_handler",
    "handler": "left_for_handler",
    "failed": "left_for_handler",
}

_ACTIVE_CLAIM_ID: ContextVar[str | None] = ContextVar("_ACTIVE_CLAIM_ID", default=None)
_QUEUE_CAP: ContextVar[int | None] = ContextVar("_QUEUE_CAP", default=None)
_QUEUE_TARGET_CLAIMS: ContextVar[list[str] | None] = ContextVar(
    "_QUEUE_TARGET_CLAIMS", default=None
)
_SUBAGENT_LLM: ContextVar[BaseChatModel | None] = ContextVar(
    "_SUBAGENT_LLM", default=None
)
_PARENT_THREAD_ID: ContextVar[str] = ContextVar(
    "_PARENT_THREAD_ID", default="queue-run"
)


def backend() -> httpx.Client:
    """Return a client for the UnderCover backend."""
    cfg = get_agent_config()
    return httpx.Client(base_url=cfg.backend_url, timeout=30)


def get_backend_client() -> httpx.Client:
    """Resolve the active backend client factory (supporting test monkeypatching)."""
    main_mod = sys.modules.get("agent.main")
    if main_mod is not None and hasattr(main_mod, "backend"):
        factory: Callable[[], httpx.Client] = main_mod.backend
        return factory()
    return backend()


def log_step(client: httpx.Client, message: str, claim_id: str | None = None) -> None:
    """Record a progress step on the active claim if a claim ID is known."""
    target_claim_id = claim_id or _ACTIVE_CLAIM_ID.get()
    if target_claim_id is None:
        return
    response = client.post(
        f"/api/claims/{target_claim_id}/steps",
        json={"message": message},
    )
    response.raise_for_status()


@wrap_model_call
def model_retry_middleware(
    request: ModelRequest[Any],
    handler: Callable[[ModelRequest[Any]], ModelCallResult[Any]],
) -> ModelCallResult[Any]:
    """Retry transient model provider errors up to the configured max_retries."""
    max_retries = max(1, get_agent_config().model_max_retries)
    for _ in range(max_retries - 1):
        try:
            return handler(request)
        except Exception as exc:
            _last_error = exc
    return handler(request)


@wrap_tool_call
def tool_error_boundary_middleware(
    request: ToolCallRequest,
    handler: Callable[[ToolCallRequest], ToolMessage | Command[Any]],
) -> ToolMessage | Command[Any]:
    """Catch tool execution exceptions and return a structured ToolMessage error."""
    try:
        return handler(request)
    except Exception as exc:
        tool_name = str(request.tool_call.get("name", "tool"))
        call_id = str(request.tool_call.get("id", "tool-error"))
        return ToolMessage(
            content=f"Error in {tool_name}: {exc}",
            tool_call_id=call_id,
        )


@tool
def check_backend() -> str:
    """Check whether the UnderCover backend is running."""
    with get_backend_client() as client:
        response = client.get("/api/health")
    response.raise_for_status()
    return str(response.json()["status"])


@tool
def get_claim(claim_id: str) -> dict[str, Any]:
    """Fetch the claim record including policy_id, customer_id, and story."""
    _ACTIVE_CLAIM_ID.set(claim_id)
    with get_backend_client() as client:
        log_step(client, f"Reading claim {claim_id}", claim_id)
        response = client.get(f"/api/claims/{claim_id}")
    response.raise_for_status()
    data: dict[str, Any] = response.json()
    return data


@tool
def get_policy(policy_id: str) -> dict[str, Any]:
    """Fetch the policy record by policy_id (such as POL-2001) and plan limits."""
    with get_backend_client() as client:
        response = client.get(f"/api/policies/{policy_id}")
        if response.is_error:
            return {
                "error": (
                    f"Policy {policy_id} not found. Call get_claim first and pass "
                    "its policy_id (such as POL-2001)."
                )
            }
        log_step(client, f"Checking policy {policy_id} and plan limits")
    data: dict[str, Any] = response.json()
    return data


@tool
def get_customer(customer_id: str) -> dict[str, Any]:
    """Fetch the customer profile and prior claims by customer_id (CUS-3001)."""
    with get_backend_client() as client:
        response = client.get(f"/api/customers/{customer_id}")
        if response.is_error:
            return {
                "error": (
                    f"Customer {customer_id} not found. Call get_claim first and "
                    "pass its customer_id (such as CUS-3001)."
                )
            }
        log_step(client, f"Reviewing customer claim history for {customer_id}")
    data: dict[str, Any] = response.json()
    return data


@tool
def get_policy_wording() -> dict[str, Any]:
    """Fetch the contractual policy wording document."""
    with get_backend_client() as client:
        log_step(client, "Reading policy wording")
        response = client.get("/api/policy-wording")
    response.raise_for_status()
    data: dict[str, Any] = response.json()
    return data


@tool
def list_document_sections(doc_name: str) -> list[dict[str, Any]]:
    """List the section IDs and titles in policy_wording or claims_manual."""
    with get_backend_client() as client:
        response = client.get(f"/api/documents/{doc_name}/sections")
        if response.is_error:
            return [{"error": f"Document {doc_name} not found."}]
    data: list[dict[str, Any]] = response.json()
    return data


@tool
def search_documents(query: str) -> list[dict[str, Any]]:
    """Search across the policy wording and claims manual for matching sections."""
    with get_backend_client() as client:
        log_step(client, f"Searching wording and manual for '{query}'")
        response = client.post("/api/documents/search", json={"query": query})
    response.raise_for_status()
    data: list[dict[str, Any]] = response.json()
    return data


@tool
def read_document_section(doc_name: str, section_id: str) -> dict[str, Any]:
    """Read a specific section of policy_wording or claims_manual and record it."""
    active_claim = _ACTIVE_CLAIM_ID.get()
    with get_backend_client() as client:
        if active_claim:
            response = client.post(
                f"/api/claims/{active_claim}/sections-read",
                json={"doc_name": doc_name, "section_id": section_id},
            )
        else:
            response = client.get(f"/api/documents/{doc_name}/sections/{section_id}")
        if response.is_error:
            return {"error": f"Section '{section_id}' not found in {doc_name}."}
    data: dict[str, Any] = response.json()
    return data


@tool
def decide_claim(
    claim_id: str,
    decision: str,
    payout: float,
    policy_section: str,
    reason: str,
) -> dict[str, Any]:
    """Record the decision, payout amount, policy section, and explanation."""
    _ACTIVE_CLAIM_ID.set(claim_id)
    normalized = _DECISION_ALIASES.get(
        decision.strip().lower(), decision.strip().lower()
    )
    with get_backend_client() as client:
        log_step(
            client,
            f"Recording decision: {normalized} (${payout:,.2f})",
            claim_id,
        )
        response = client.post(
            f"/api/claims/{claim_id}/decision",
            json={
                "decision": normalized,
                "payout": payout,
                "policy_section": policy_section,
                "reason": reason,
            },
        )
        if response.status_code == HTTP_CONFLICT:
            return {
                "status": "already_decided",
                "detail": str(response.json().get("detail", "")),
            }
    response.raise_for_status()
    data: dict[str, Any] = response.json()
    return data


@tool
def pay_claim(claim_id: str, amount: float) -> dict[str, Any]:
    """Request payment of an approved payout amount for a claim."""
    _ACTIVE_CLAIM_ID.set(claim_id)
    with get_backend_client() as client:
        log_step(client, f"Requesting payout of ${amount:,.2f}", claim_id)
        response = client.post(
            f"/api/claims/{claim_id}/pay",
            json={"amount": amount},
        )
        if response.status_code == HTTP_CONFLICT:
            detail = str(response.json().get("detail", ""))
            if "sign-off" in detail.lower():
                log_step(
                    client,
                    f"Payment of ${amount:,.2f} held pending handler sign-off",
                    claim_id,
                )
                return {
                    "status": "pending_sign_off",
                    "detail": detail,
                }
            return {"status": "conflict", "detail": detail}
    response.raise_for_status()
    data: dict[str, Any] = response.json()
    return data


def resolve_target_claims(client: httpx.Client) -> list[dict[str, Any]]:
    """Return the waiting claims within the current queue run's cap."""
    all_claims: list[dict[str, Any]] = client.get("/api/claims").json()
    locked_ids = _QUEUE_TARGET_CLAIMS.get()
    cap = _QUEUE_CAP.get()
    if locked_ids is None:
        waiting = [c for c in all_claims if c["status"] == "waiting"]
        selected = waiting[:cap] if cap is not None else waiting
        locked_ids = [str(c["claim_id"]) for c in selected]
        _QUEUE_TARGET_CLAIMS.set(locked_ids)
    id_set = set(locked_ids)
    return [c for c in all_claims if c["claim_id"] in id_set]


@tool
def get_waiting_claims() -> list[dict[str, Any]]:
    """Return the waiting claims in the queue within the current run's cap."""
    with get_backend_client() as client:
        targets = resolve_target_claims(client)
    return [
        {
            "claim_id": c["claim_id"],
            "claim_type": c["claim_type"],
            "amount_claimed": c["amount_claimed"],
            "summary": c["summary"],
            "status": c["status"],
            "attempts": c.get("attempts", 0),
        }
        for c in targets
        if c["status"] == "waiting"
    ]


@tool
def write_todos(todos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Save or update the queue agent's to-do list for the current run."""
    normalized_todos: list[dict[str, str]] = []
    for item in todos:
        raw_status = str(item.get("status", "to_do")).strip().lower()
        status = _TODO_STATUS_ALIASES.get(raw_status, "to_do")
        claim_id = str(item.get("claim_id", "")).strip()
        desc = str(
            item.get("description") or item.get("content") or f"Decide {claim_id}"
        )
        if not claim_id and "CLM-" in desc:
            for token in desc.replace(":", " ").split():
                if token.startswith("CLM-"):
                    claim_id = token
                    break
        normalized_todos.append(
            {
                "claim_id": claim_id or "QUEUE",
                "description": desc,
                "status": status,
                "result_summary": str(item.get("result_summary", "")),
            }
        )
    with get_backend_client() as client:
        response = client.put("/api/todos", json={"todos": normalized_todos})
    response.raise_for_status()
    data: list[dict[str, Any]] = response.json()
    return data


def sync_todo_item(
    client: httpx.Client,
    claim_id: str,
    status: str,
    result_summary: str,
    description: str = "",
) -> None:
    """Ensure the claim's to-do item reflects its current execution state."""
    client.put(
        f"/api/todos/{claim_id}",
        json={
            "description": description,
            "status": status,
            "result_summary": result_summary,
        },
    ).raise_for_status()


@tool
def check_missed_claims() -> str:
    """Check whether any waiting claim within the run's cap was missed."""
    with get_backend_client() as client:
        targets = resolve_target_claims(client)
    remaining = [
        str(c["claim_id"]) for c in targets if c["status"] in ("waiting", "in_progress")
    ]
    if not remaining:
        return "All target claims within the cap have been processed."
    return f"Missed or pending claims remaining within cap: {', '.join(remaining)}"


CLAIM_AGENT_TOOLS = [
    check_backend,
    get_claim,
    get_policy,
    get_customer,
    list_document_sections,
    search_documents,
    read_document_section,
    decide_claim,
    pay_claim,
]
