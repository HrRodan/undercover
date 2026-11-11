"""The UnderCover Agent and Subagent Harness."""

import os
from typing import Any, Literal

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import SecretStr

from agent.config import get_agent_config
from agent.tools import (
    _ACTIVE_CLAIM_ID,
    _PARENT_THREAD_ID,
    _QUEUE_CAP,
    _QUEUE_TARGET_CLAIMS,
    _SUBAGENT_LLM,
    CLAIM_AGENT_TOOLS,
    HTTP_CONFLICT,
    MAX_ATTEMPTS_BEFORE_HANDLER,
    backend,
    check_backend,
    check_missed_claims,
    decide_claim,
    get_backend_client,
    get_claim,
    get_customer,
    get_policy,
    get_policy_wording,
    get_waiting_claims,
    list_document_sections,
    model_retry_middleware,
    pay_claim,
    read_document_section,
    resolve_target_claims,
    search_documents,
    sync_todo_item,
    tool_error_boundary_middleware,
    write_todos,
)

load_dotenv(override=True)

__all__ = [
    "CLAIM_AGENT_TOOLS",
    "HTTP_CONFLICT",
    "MAX_ATTEMPTS_BEFORE_HANDLER",
    "QUEUE_AGENT_TOOLS",
    "backend",
    "check_backend",
    "check_missed_claims",
    "decide_claim",
    "fetch_instructions",
    "get_claim",
    "get_customer",
    "get_policy",
    "get_policy_wording",
    "get_waiting_claims",
    "list_document_sections",
    "model",
    "model_retry_middleware",
    "pay_claim",
    "read_document_section",
    "run",
    "run_queue",
    "search_documents",
    "tool_error_boundary_middleware",
    "work_claim",
    "write_todos",
]


def _precheck_claim_for_subagent(claim_id: str) -> tuple[dict[str, Any] | None, str]:
    """Validate cap and claim state before subagent run; return (claim, early_msg)."""
    locked_ids = _QUEUE_TARGET_CLAIMS.get()
    if locked_ids is not None and claim_id not in locked_ids:
        return None, f"{claim_id}: outside the current run cap; left waiting."

    with get_backend_client() as client:
        claim_res = client.get(f"/api/claims/{claim_id}")
        if claim_res.is_error:
            return None, f"{claim_id}: claim not found."
        claim: dict[str, Any] = claim_res.json()
        if claim["status"] in ("decided", "waiting_for_sign_off") and (
            claim["decision"] is not None
        ):
            payout_val = float(claim["payout"] or 0.0)
            summary = f"{claim_id}: already {claim['decision']} (${payout_val:,.2f})"
            sync_todo_item(client, claim_id, "done", summary)
            return None, summary
        if claim["status"] == "left_for_handler" or (
            int(claim.get("attempts", 0)) >= MAX_ATTEMPTS_BEFORE_HANDLER
        ):
            summary = f"{claim_id}: left for a handler after two failed attempts."
            sync_todo_item(client, claim_id, "left_for_handler", summary)
            return None, summary
        sync_todo_item(client, claim_id, "in_progress", "Working claim")
        return claim, ""


def _execute_claim_subagent(
    claim_id: str,
    config: RunnableConfig | None = None,
) -> str:
    """Run a fresh subagent on one claim with automatic failure recovery."""
    claim, early_msg = _precheck_claim_for_subagent(claim_id)
    if claim is None:
        return early_msg

    attempt_num = int(claim.get("attempts", 0)) + 1
    parent_thread = _PARENT_THREAD_ID.get()
    sub_thread_id = f"{parent_thread}-{claim_id}-attempt-{attempt_num}"
    sub_llm = _SUBAGENT_LLM.get()

    try:
        run(
            claim_id,
            sub_thread_id,
            llm=sub_llm,
            parent_config=config,
        )
    except Exception as exc:
        return _handle_subagent_failure(claim_id, str(exc))

    with get_backend_client() as client:
        updated = client.get(f"/api/claims/{claim_id}").json()
        if updated["decision"] is None or updated["status"] in (
            "waiting",
            "in_progress",
        ):
            return _handle_subagent_failure(
                claim_id, "Subagent finished without recording a decision"
            )
        payout_val = float(updated["payout"] or 0.0)
        summary = (
            f"{claim_id}: {updated['decision']} (${payout_val:,.2f}) "
            f"[{updated['status']}]"
        )
        sync_todo_item(client, claim_id, "done", summary)
        return summary


def _handle_subagent_failure(claim_id: str, error_text: str) -> str:
    """Record a failed claim attempt in the backend and return a one-line status."""
    with get_backend_client() as client:
        fail_res = client.post(
            f"/api/claims/{claim_id}/fail",
            json={"error": error_text},
        )
        fail_res.raise_for_status()
        failed_claim = fail_res.json()
        attempts = int(failed_claim.get("attempts", 1))
        if failed_claim["status"] == "left_for_handler":
            msg = (
                f"{claim_id}: failed twice (attempt {attempts}: {error_text}); "
                "left for a handler."
            )
            sync_todo_item(client, claim_id, "left_for_handler", msg)
            return msg
        msg = (
            f"{claim_id}: failed on attempt {attempts} ({error_text}); "
            "returned to waiting queue to retry."
        )
        sync_todo_item(client, claim_id, "to_do", msg)
        return msg


@tool
def work_claim(claim_id: str, config: RunnableConfig) -> str:
    """Delegate one claim to a fresh claim-handler subagent and return its result."""
    return _execute_claim_subagent(claim_id, config=config)


QUEUE_AGENT_TOOLS = [
    get_waiting_claims,
    write_todos,
    work_claim,
    check_missed_claims,
]


def fetch_instructions(
    role: Literal["claim", "queue"] = "claim",
) -> str:
    """Fetch the read-only system prompt for the queue or claim agent."""
    with get_backend_client() as client:
        response = client.get("/api/instructions")
    response.raise_for_status()
    payload = response.json()
    if role == "queue" and payload.get("queue_instructions"):
        return str(payload["queue_instructions"])
    if role == "claim" and payload.get("claim_instructions"):
        return str(payload["claim_instructions"])
    return str(payload["instructions"])


def model(
    role: Literal["claim", "queue"] = "claim",
    reasoning_effort: str | None = None,
) -> ChatOpenAI:
    """Return the configured OpenRouter ChatOpenAI model for the given role."""
    cfg = get_agent_config()
    chosen_model = cfg.queue_model_name if role == "queue" else cfg.claim_model_name
    default_effort = (
        cfg.queue_reasoning_effort if role == "queue" else cfg.claim_reasoning_effort
    )
    effort = reasoning_effort if reasoning_effort is not None else default_effort
    return ChatOpenAI(
        model=chosen_model,
        base_url=cfg.openrouter_base_url,
        api_key=SecretStr(os.environ.get("OPENROUTER_API_KEY", "missing-key")),
        reasoning_effort=effort,
        timeout=cfg.model_timeout_seconds,
        max_retries=cfg.model_max_retries,
    )


def run(
    claim_id: str,
    thread_id: str,
    llm: BaseChatModel | None = None,
    parent_config: RunnableConfig | None = None,
) -> str:
    """Run a fresh subagent on one claim and return its final one-line reply."""
    token = _ACTIVE_CLAIM_ID.set(claim_id)
    try:
        instructions = fetch_instructions("claim")
        cfg = get_agent_config()
        agent = create_agent(
            llm or model("claim"),
            tools=CLAIM_AGENT_TOOLS,
            system_prompt=instructions,
            checkpointer=InMemorySaver(),
            middleware=[model_retry_middleware, tool_error_boundary_middleware],
        )
        invoke_config: RunnableConfig = {
            "run_name": f"undercover_claim_subagent_{claim_id}",
            "tags": ["undercover", "claim-subagent", claim_id],
            "metadata": {
                "claim_id": claim_id,
                "thread_id": thread_id,
                "parent_thread_id": _PARENT_THREAD_ID.get(),
            },
            "recursion_limit": cfg.recursion_limit,
            "configurable": {"thread_id": thread_id},
        }
        if parent_config and "callbacks" in parent_config:
            invoke_config["callbacks"] = parent_config["callbacks"]
        result = agent.invoke(
            {"messages": [{"role": "user", "content": f"Claim {claim_id}"}]},
            config=invoke_config,
        )
        return str(result["messages"][-1].text)
    finally:
        _ACTIVE_CLAIM_ID.reset(token)


def _reconcile_missed_target_claims(
    parent_config: RunnableConfig,
) -> list[str]:
    """Ensure every target claim within the cap is tried up to 2 times."""
    notes: list[str] = []
    for _pass in range(MAX_ATTEMPTS_BEFORE_HANDLER):
        with get_backend_client() as client:
            targets = resolve_target_claims(client)
        pending = [
            str(c["claim_id"])
            for c in targets
            if c["status"] in ("waiting", "in_progress")
        ]
        if not pending:
            break
        for cid in pending:
            notes.append(_execute_claim_subagent(cid, config=parent_config))
    return notes


def run_queue(
    thread_id: str = "queue-run",
    cap: int | None = None,
    llm: BaseChatModel | None = None,
    subagent_llm: BaseChatModel | None = None,
) -> str:
    """Run the master queue agent across waiting claims up to cap."""
    cap_token = _QUEUE_CAP.set(cap)
    targets_token = _QUEUE_TARGET_CLAIMS.set(None)
    sub_llm_token = _SUBAGENT_LLM.set(subagent_llm or llm)
    thread_token = _PARENT_THREAD_ID.set(thread_id)
    try:
        effective_cap = cap if cap is not None else 25
        with get_backend_client() as client:
            targets = resolve_target_claims(client)
            target_ids = [str(c["claim_id"]) for c in targets]
            initial_todos = [
                {
                    "claim_id": cid,
                    "description": f"Decide claim {cid}",
                    "status": "to_do",
                    "result_summary": "",
                }
                for cid in target_ids
            ]
            client.put("/api/todos", json={"todos": initial_todos})
            client.put(
                "/api/queue-run",
                json={
                    "status": "running",
                    "cap": effective_cap,
                    "summary": "",
                    "target_claims": target_ids,
                },
            )

        instructions = fetch_instructions("queue")
        cfg = get_agent_config()
        queue_agent = create_agent(
            llm or model("queue"),
            tools=QUEUE_AGENT_TOOLS,
            system_prompt=instructions,
            checkpointer=InMemorySaver(),
            middleware=[model_retry_middleware, tool_error_boundary_middleware],
        )
        prompt = (
            f"Work the waiting claims queue (capped at {cap} claims)."
            if cap is not None
            else "Work all waiting claims in the queue."
        )
        invoke_config: RunnableConfig = {
            "run_name": "undercover_queue_agent",
            "tags": ["undercover", "queue-agent"],
            "metadata": {"thread_id": thread_id, "cap": cap},
            "recursion_limit": cfg.recursion_limit,
            "configurable": {"thread_id": thread_id},
        }
        result = queue_agent.invoke(
            {"messages": [{"role": "user", "content": prompt}]},
            config=invoke_config,
        )
        final_text = str(result["messages"][-1].text)
        reconciled = _reconcile_missed_target_claims(invoke_config)
        summary = (
            "\n".join(reconciled)
            if reconciled and not final_text.strip()
            else final_text
        )
        with get_backend_client() as client:
            client.put(
                "/api/queue-run",
                json={
                    "status": "completed",
                    "cap": effective_cap,
                    "summary": summary,
                    "target_claims": target_ids,
                },
            )
        return summary
    finally:
        _QUEUE_CAP.reset(cap_token)
        _QUEUE_TARGET_CLAIMS.reset(targets_token)
        _SUBAGENT_LLM.reset(sub_llm_token)
        _PARENT_THREAD_ID.reset(thread_token)
