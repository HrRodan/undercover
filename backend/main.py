"""The UnderCover backend REST API."""

from typing import Annotated

from fastapi import Depends, FastAPI
from sqlalchemy.orm import Session

from agent import main as agent_main
from backend import db
from backend.schemas import (
    ClaimDetail,
    ClaimsManualResponse,
    ClaimSummary,
    ConfigResponse,
    CustomerDetail,
    DecisionRequest,
    DocumentSearchRequest,
    DocumentSectionDetail,
    DocumentSectionSummary,
    FailClaimRequest,
    HandlerDetail,
    InstructionsResponse,
    PayRequest,
    PolicyDetail,
    PolicyWordingResponse,
    QueueRunRequest,
    QueueRunStateUpdateRequest,
    QueueRunStatusResponse,
    SectionReadRequest,
    SignOffRequest,
    SingleTodoUpdateRequest,
    StepRequest,
    TodoItemSchema,
    TodoListUpdateRequest,
)

app = FastAPI(title="UnderCover")

DbSession = Annotated[Session, Depends(db.get_session)]


@app.get("/api/health", operation_id="health")
def health() -> dict[str, str]:
    """Check that the backend is running."""
    return {"status": "ok"}


@app.get("/api/config", operation_id="get_config")
def get_config() -> ConfigResponse:
    """Return the active file and model configuration for the platform."""
    return db.get_config_response()


@app.get("/api/claims", operation_id="list_claims")
def list_claims(session: DbSession) -> list[ClaimSummary]:
    """Return all claims in queue order."""
    return db.list_claims(session)


@app.get("/api/claims/{claim_id}", operation_id="get_claim")
def get_claim(claim_id: str, session: DbSession) -> ClaimDetail:
    """Return the full claim record including steps and documents."""
    return db.get_claim_detail(session, claim_id)


@app.get("/api/policies/{policy_id}", operation_id="get_policy")
def get_policy(policy_id: str, session: DbSession) -> PolicyDetail:
    """Return a policy with its plan limits and add-on details."""
    return db.get_policy_detail(session, policy_id)


@app.get("/api/customers/{customer_id}", operation_id="get_customer")
def get_customer(customer_id: str, session: DbSession) -> CustomerDetail:
    """Return a customer profile and prior claim history."""
    return db.get_customer_detail(session, customer_id)


@app.get("/api/handlers", operation_id="list_handlers")
def list_handlers(session: DbSession) -> list[HandlerDetail]:
    """Return all claims handlers."""
    return db.list_handlers(session)


@app.get("/api/policy-wording", operation_id="get_policy_wording")
def get_policy_wording(session: DbSession) -> PolicyWordingResponse:
    """Return the active contractual policy wording."""
    return db.get_policy_wording_doc(session)


@app.get("/api/claims-manual", operation_id="get_claims_manual")
def get_claims_manual(session: DbSession) -> ClaimsManualResponse:
    """Return the active internal claims handling manual."""
    return db.get_claims_manual_doc(session)


@app.get(
    "/api/documents/{doc_name}/sections",
    operation_id="list_document_sections",
)
def list_document_sections(
    doc_name: str, session: DbSession
) -> list[DocumentSectionSummary]:
    """List section identifiers and titles for the policy wording or claims manual."""
    return db.list_document_sections(session, doc_name)


@app.get(
    "/api/documents/{doc_name}/sections/{section_id}",
    operation_id="get_document_section",
)
def get_document_section(
    doc_name: str, section_id: str, session: DbSession
) -> DocumentSectionDetail:
    """Return a single section of the policy wording or claims manual."""
    return db.get_document_section(session, doc_name, section_id)


@app.post(
    "/api/documents/search",
    operation_id="search_document_sections",
)
def search_document_sections(
    payload: DocumentSearchRequest, session: DbSession
) -> list[DocumentSectionDetail]:
    """Search across the policy wording and claims manual for matching sections."""
    return db.search_document_sections(session, payload.query)


@app.post(
    "/api/claims/{claim_id}/sections-read",
    operation_id="record_claim_section_read",
)
def record_claim_section_read(
    claim_id: str, payload: SectionReadRequest, session: DbSession
) -> DocumentSectionDetail:
    """Read a document section and record it on the specified claim."""
    return db.record_claim_section_read(
        session, claim_id, payload.doc_name, payload.section_id
    )


@app.get("/api/instructions", operation_id="get_instructions")
def get_instructions(session: DbSession) -> InstructionsResponse:
    """Return the read-only system instructions for the UnderCover Agent."""
    return db.get_instructions_doc(session)


@app.get("/api/todos", operation_id="get_todos")
def get_todos(session: DbSession) -> list[TodoItemSchema]:
    """Return the queue agent's to-do list for the active run."""
    return db.get_todos(session)


@app.put("/api/todos", operation_id="save_todos")
def save_todos(
    payload: TodoListUpdateRequest, session: DbSession
) -> list[TodoItemSchema]:
    """Replace the queue agent's to-do list with the provided items."""
    return db.save_todos(session, payload.todos)


@app.put("/api/todos/{claim_id}", operation_id="update_single_todo")
def update_single_todo(
    claim_id: str, payload: SingleTodoUpdateRequest, session: DbSession
) -> TodoItemSchema:
    """Atomically update or insert a single claim's to-do item."""
    return db.update_single_todo(
        session,
        claim_id,
        payload.status,
        payload.result_summary,
        payload.description,
    )


@app.get("/api/queue-run", operation_id="get_queue_run")
def get_queue_run(session: DbSession) -> QueueRunStatusResponse:
    """Return the status, cap, to-do list, and summary of the queue run."""
    return db.get_queue_run_status(session)


@app.put("/api/queue-run", operation_id="update_queue_run")
def update_queue_run(
    payload: QueueRunStateUpdateRequest, session: DbSession
) -> QueueRunStatusResponse:
    """Update the persisted status, cap, target claims, and summary of the queue run."""
    return db.set_queue_run_state(
        session,
        status=payload.status,
        cap=payload.cap,
        summary=payload.summary,
        target_claims=payload.target_claims,
    )


@app.post("/api/claims/{claim_id}/steps", operation_id="record_claim_step")
def record_claim_step(
    claim_id: str, payload: StepRequest, session: DbSession
) -> ClaimDetail:
    """Record a progress step while the agent works on a claim."""
    return db.record_step(session, claim_id, payload.message)


@app.post("/api/claims/{claim_id}/decision", operation_id="decide_claim")
def decide_claim(
    claim_id: str, payload: DecisionRequest, session: DbSession
) -> ClaimDetail:
    """Record the agent's decision, payout, policy section, and explanation."""
    return db.record_decision(session, claim_id, payload)


@app.post("/api/claims/{claim_id}/pay", operation_id="pay_claim")
def pay_claim(claim_id: str, payload: PayRequest, session: DbSession) -> ClaimDetail:
    """Pay an approved claim if within the $1,000 limit or signed off by a handler."""
    return db.pay_claim_amount(session, claim_id, payload.amount)


@app.post("/api/claims/{claim_id}/fail", operation_id="fail_claim")
def fail_claim(
    claim_id: str, payload: FailClaimRequest, session: DbSession
) -> ClaimDetail:
    """Record a failed attempt on a claim and reset or leave for a handler."""
    return db.fail_claim_attempt(session, claim_id, payload.error)


@app.post("/api/claims/{claim_id}/sign-off", operation_id="sign_off_claim")
def sign_off_claim(
    claim_id: str, payload: SignOffRequest, session: DbSession
) -> ClaimDetail:
    """Record a handler's sign-off on an approved claim over $1,000 and pay it."""
    return db.sign_off_claim_payout(session, claim_id, payload.handler_id)


def invoke_claim_agent(claim_id: str) -> None:
    """Invoke the UnderCover Agent for the given claim ID."""
    agent_main.run(claim_id, f"thread-{claim_id}")


def invoke_queue_agent(cap: int) -> str:
    """Invoke the UnderCover Queue Agent for up to cap waiting claims."""
    return agent_main.run_queue(f"queue-run-{cap}", cap=cap)


@app.post("/api/claims/{claim_id}/run", operation_id="run_claim_agent")
def run_claim_agent(claim_id: str, session: DbSession) -> ClaimDetail:
    """Reset steps, mark a claim in progress, and run the UnderCover Agent."""
    db.prepare_claim_for_run(session, claim_id)
    session.close()
    try:
        invoke_claim_agent(claim_id)
    except Exception as exc:
        session.expire_all()
        return db.fail_claim_attempt(session, claim_id, str(exc))
    session.expire_all()
    detail = db.get_claim_detail(session, claim_id)
    if detail.status == "in_progress" and detail.decision is None:
        return db.fail_claim_attempt(
            session, claim_id, "Agent finished without recording a decision"
        )
    return detail


@app.post("/api/queue/run", operation_id="run_claims_queue")
def run_claims_queue(
    payload: QueueRunRequest, session: DbSession
) -> QueueRunStatusResponse:
    """Run the UnderCover Queue Agent across waiting claims up to the given cap."""
    effective_cap = max(1, payload.cap)
    waiting_ids = [
        c.claim_id for c in db.list_claims(session) if c.status == "waiting"
    ][:effective_cap]
    db.set_queue_run_state(
        session,
        status="running",
        cap=effective_cap,
        summary="",
        target_claims=waiting_ids,
    )
    session.close()
    try:
        summary = invoke_queue_agent(effective_cap)
    except Exception as exc:
        session.expire_all()
        return db.set_queue_run_state(
            session,
            status="failed",
            cap=effective_cap,
            summary=f"Queue run failed: {exc}",
            target_claims=waiting_ids,
        )
    session.expire_all()
    return db.set_queue_run_state(
        session,
        status="completed",
        cap=effective_cap,
        summary=summary,
        target_claims=waiting_ids,
    )


@app.post("/api/claims/reset", operation_id="reset_claims")
def reset_claims(session: DbSession) -> list[ClaimSummary]:
    """Reset all claims and steps in the queue back to their waiting state."""
    return db.reset_claims(session)
