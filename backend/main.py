"""The UnderCover backend REST API."""

from typing import Annotated

from fastapi import Depends, FastAPI
from sqlalchemy.orm import Session

from agent import main as agent_main
from backend import db
from backend.schemas import (
    ClaimDetail,
    ClaimSummary,
    CustomerDetail,
    DecisionRequest,
    HandlerDetail,
    InstructionsResponse,
    PayRequest,
    PolicyDetail,
    PolicyWordingResponse,
    SignOffRequest,
    StepRequest,
)

app = FastAPI(title="UnderCover")

DbSession = Annotated[Session, Depends(db.get_session)]


@app.get("/api/health", operation_id="health")
def health() -> dict[str, str]:
    """Check that the backend is running."""
    return {"status": "ok"}


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


@app.get("/api/instructions", operation_id="get_instructions")
def get_instructions(session: DbSession) -> InstructionsResponse:
    """Return the read-only system instructions for the UnderCover Agent."""
    return db.get_instructions_doc(session)


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


@app.post("/api/claims/{claim_id}/sign-off", operation_id="sign_off_claim")
def sign_off_claim(
    claim_id: str, payload: SignOffRequest, session: DbSession
) -> ClaimDetail:
    """Record a handler's sign-off on an approved claim over $1,000 and pay it."""
    return db.sign_off_claim_payout(session, claim_id, payload.handler_id)


def invoke_claim_agent(claim_id: str) -> None:
    """Invoke the UnderCover Agent for the given claim ID."""
    agent_main.run(claim_id, f"thread-{claim_id}")


@app.post("/api/claims/{claim_id}/run", operation_id="run_claim_agent")
def run_claim_agent(claim_id: str, session: DbSession) -> ClaimDetail:
    """Reset steps, mark a claim in progress, and run the UnderCover Agent."""
    db.prepare_claim_for_run(session, claim_id)
    invoke_claim_agent(claim_id)
    session.expire_all()
    return db.get_claim_detail(session, claim_id)


@app.post("/api/claims/reset", operation_id="reset_claims")
def reset_claims(session: DbSession) -> list[ClaimSummary]:
    """Reset all claims and steps in the queue back to their waiting state."""
    return db.reset_claims(session)
