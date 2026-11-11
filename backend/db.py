"""SQLAlchemy database engine, session management, and ORM operations."""

import json
import threading
from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import Engine, create_engine, delete, inspect, select
from sqlalchemy.orm import Session

from backend import documents
from backend.config import DEFAULT_DATA_DIR, get_backend_config
from backend.models import (
    Base,
    ClaimRecord,
    ClaimStepRecord,
    CompanyRecord,
    HandlerRecord,
    QueueRunRecord,
    TodoItemRecord,
)
from backend.queries import (
    claim_to_detail,
    claim_to_summary,
    get_approval_limit,
    get_claim_detail,
    get_claim_or_404,
    get_config_response,
    get_customer_detail,
    get_policy_detail,
    list_claims,
    list_handlers,
)
from backend.schemas import (
    ClaimDetail,
    ClaimsManualResponse,
    ClaimSummary,
    DecisionRequest,
    DocumentSectionDetail,
    DocumentSectionSummary,
    InstructionsResponse,
    PolicyWordingResponse,
    QueueRunStatusResponse,
    TodoItemSchema,
    TodoStatus,
)
from backend.seed import (
    CLAIM_INSTRUCTIONS,
    DEFAULT_INSTRUCTIONS,
    QUEUE_INSTRUCTIONS,
    seed_all,
    sync_docs_and_instructions,
)

DATA_DIR = DEFAULT_DATA_DIR

_ENGINES: dict[str, Engine] = {}
_INIT_LOCK = threading.Lock()
_WRITE_LOCK = threading.RLock()
_MAX_ATTEMPTS_BEFORE_HANDLER = 2
_VALID_TODO_STATUSES: dict[str, TodoStatus] = {
    "to_do": "to_do",
    "in_progress": "in_progress",
    "done": "done",
    "left_for_handler": "left_for_handler",
}

__all__ = [
    "CLAIM_INSTRUCTIONS",
    "DATA_DIR",
    "DEFAULT_INSTRUCTIONS",
    "QUEUE_INSTRUCTIONS",
    "claim_to_detail",
    "claim_to_summary",
    "get_approval_limit",
    "get_claim_detail",
    "get_claim_or_404",
    "get_config_response",
    "get_customer_detail",
    "get_policy_detail",
    "list_claims",
    "list_handlers",
]


def get_db_path() -> Path:
    """Return the configured SQLite database file path."""
    return get_backend_config().db_path


def get_engine() -> Engine:
    """Return a cached SQLAlchemy engine for the current database path."""
    db_path = get_db_path().resolve()
    url = f"sqlite:///{db_path}"
    with _INIT_LOCK:
        if url not in _ENGINES:
            db_path.parent.mkdir(parents=True, exist_ok=True)
            _ENGINES[url] = create_engine(
                url, connect_args={"check_same_thread": False, "timeout": 30}
            )
        return _ENGINES[url]


def _schema_needs_upgrade(engine: Engine) -> bool:
    """Return True if an existing pre-Day-5 database is missing new columns."""
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    if "claims" not in tables or "instructions" not in tables:
        return False
    claim_cols = {col["name"] for col in inspector.get_columns("claims")}
    instr_cols = {col["name"] for col in inspector.get_columns("instructions")}
    return "attempts" not in claim_cols or "queue_instructions" not in instr_cols


def init_db(engine: Engine | None = None) -> None:
    """Create database tables and seed initial operational data if empty."""
    target_engine = engine or get_engine()
    with _INIT_LOCK:
        if _schema_needs_upgrade(target_engine):
            Base.metadata.drop_all(target_engine)
        Base.metadata.create_all(target_engine)
        with Session(target_engine) as session:
            existing = session.scalar(
                select(CompanyRecord).where(CompanyRecord.id == 1)
            )
            if existing is not None:
                return
            seed_all(session)
            session.commit()


def get_session() -> Generator[Session, None, None]:
    """Yield a SQLAlchemy session with initialized schema and seed data."""
    engine = get_engine()
    init_db(engine)
    with Session(engine) as session:
        yield session


def reset_db(engine: Engine | None = None) -> None:
    """Drop all database tables and re-seed initial operational records."""
    target_engine = engine or get_engine()
    with _INIT_LOCK:
        Base.metadata.drop_all(target_engine)
    init_db(target_engine)


def reset_claims(session: Session) -> list[ClaimSummary]:
    """Reset all claims, steps, todos, and queue run state back to waiting."""
    with _WRITE_LOCK:
        session.execute(delete(ClaimStepRecord))
        session.execute(delete(TodoItemRecord))
        run_rec = session.scalar(select(QueueRunRecord).where(QueueRunRecord.id == 1))
        if run_rec is not None:
            run_rec.status = "idle"
            run_rec.summary = ""
            run_rec.target_claims_json = "[]"
        for claim in session.scalars(select(ClaimRecord)):
            claim.status = "waiting"
            claim.decision = None
            claim.payout = None
            claim.policy_section = None
            claim.reason = None
            claim.payment_status = "unpaid"
            claim.amount_paid = 0.0
            claim.signed_off_by = None
            claim.attempts = 0
            claim.sections_read_json = "[]"
        session.commit()
        return list_claims(session)


def update_instructions_if_default(session: Session) -> None:
    """Keep the stored instructions, policy wording, and claims manual current."""
    sync_docs_and_instructions(session, _WRITE_LOCK)


def get_policy_wording_doc(session: Session) -> PolicyWordingResponse:
    """Return the active contractual policy wording."""
    return documents.get_policy_wording_doc(session, _WRITE_LOCK)


def get_claims_manual_doc(session: Session) -> ClaimsManualResponse:
    """Return the active internal claims handling manual."""
    return documents.get_claims_manual_doc(session, _WRITE_LOCK)


def list_document_sections(
    session: Session, doc_name: str
) -> list[DocumentSectionSummary]:
    """Return section summaries (IDs and titles) for the given document."""
    return documents.list_document_sections(session, doc_name, _WRITE_LOCK)


def get_document_section(
    session: Session, doc_name: str, section_id: str
) -> DocumentSectionDetail:
    """Return a single section from policy_wording or claims_manual by ID or title."""
    return documents.get_document_section(session, doc_name, section_id, _WRITE_LOCK)


def search_document_sections(
    session: Session, query: str
) -> list[DocumentSectionDetail]:
    """Search across both policy_wording and claims_manual for matching sections."""
    return documents.search_document_sections(session, query, _WRITE_LOCK)


def record_claim_section_read(
    session: Session, claim_id: str, doc_name: str, section_id: str
) -> DocumentSectionDetail:
    """Read a document section and record on the claim that it was consulted."""
    section = get_document_section(session, doc_name, section_id)
    label_prefix = (
        "Policy Wording" if section.doc_name == "policy_wording" else "Claims Manual"
    )
    entry = f"{label_prefix} — {section.title}"
    with _WRITE_LOCK:
        claim = get_claim_or_404(session, claim_id)
        existing_read: list[str] = json.loads(claim.sections_read_json or "[]")
        if entry not in existing_read:
            existing_read.append(entry)
            claim.sections_read_json = json.dumps(existing_read)
            session.commit()
        record_step(session, claim_id, f"Reading {entry}")
    return section


def get_instructions_doc(session: Session) -> InstructionsResponse:
    """Return the read-only system prompts for the UnderCover Agent."""
    return documents.get_instructions_doc(session, _WRITE_LOCK)


def prepare_claim_for_run(session: Session, claim_id: str) -> ClaimRecord:
    """Reset steps and decision fields and mark a claim in_progress."""
    with _WRITE_LOCK:
        update_instructions_if_default(session)
        claim = get_claim_or_404(session, claim_id)
        session.execute(
            delete(ClaimStepRecord).where(ClaimStepRecord.claim_id == claim_id)
        )
        claim.status = "in_progress"
        claim.decision = None
        claim.payout = None
        claim.policy_section = None
        claim.reason = None
        claim.payment_status = "unpaid"
        claim.amount_paid = 0.0
        claim.signed_off_by = None
        claim.attempts = 0
        claim.sections_read_json = "[]"
        session.commit()
        return claim


def record_step(session: Session, claim_id: str, message: str) -> ClaimDetail:
    """Append a step to a claim and mark waiting claims as in_progress."""
    with _WRITE_LOCK:
        claim = get_claim_or_404(session, claim_id)
        if claim.status == "waiting":
            claim.status = "in_progress"
        existing_steps = list(
            session.scalars(
                select(ClaimStepRecord)
                .where(ClaimStepRecord.claim_id == claim_id)
                .order_by(ClaimStepRecord.step_number)
            )
        )
        next_number = len(existing_steps) + 1
        session.add(
            ClaimStepRecord(
                claim_id=claim_id,
                step_number=next_number,
                message=message,
                created_at=datetime.now(UTC).isoformat(),
            )
        )
        session.commit()
        return claim_to_detail(session, claim)


def record_decision(
    session: Session, claim_id: str, payload: DecisionRequest
) -> ClaimDetail:
    """Record the agent's decision on a claim and block duplicate decisions."""
    with _WRITE_LOCK:
        claim = get_claim_or_404(session, claim_id)
        if claim.decision is not None and claim.status in (
            "decided",
            "waiting_for_sign_off",
        ):
            raise HTTPException(
                status_code=409,
                detail=f"Claim {claim_id} has already been decided ({claim.decision}).",
            )
        limit = get_approval_limit(session)
        claim.decision = payload.decision
        claim.payout = payload.payout if payload.decision == "approve" else 0.0
        claim.policy_section = payload.policy_section
        claim.reason = payload.reason
        claim.signed_off_by = None
        claim.amount_paid = 0.0

        if payload.decision == "approve" and payload.payout > limit:
            claim.status = "waiting_for_sign_off"
            claim.payment_status = "pending_sign_off"
        else:
            claim.status = "decided"
            claim.payment_status = "unpaid"

        session.commit()
        return claim_to_detail(session, claim)


def pay_claim_amount(session: Session, claim_id: str, amount: float) -> ClaimDetail:
    """Pay an approved claim if within limit and not already paid."""
    with _WRITE_LOCK:
        claim = get_claim_or_404(session, claim_id)
        limit = get_approval_limit(session)
        if claim.payment_status == "paid":
            raise HTTPException(
                status_code=409,
                detail=f"Claim {claim_id} has already been paid.",
            )
        if claim.decision != "approve" or amount <= 0:
            raise HTTPException(
                status_code=409,
                detail="Only approved claims with a positive amount can be paid.",
            )
        if claim.status == "waiting_for_sign_off" or (
            amount > limit and not claim.signed_off_by
        ):
            raise HTTPException(
                status_code=409,
                detail=(
                    "Payouts over $1,000 require a handler's sign-off before payment."
                ),
            )
        claim.payment_status = "paid"
        claim.amount_paid = amount
        claim.status = "decided"
        session.commit()
        return claim_to_detail(session, claim)


def fail_claim_attempt(session: Session, claim_id: str, error: str) -> ClaimDetail:
    """Record a failed attempt: 1st resets to waiting, 2nd leaves for handler."""
    with _WRITE_LOCK:
        claim = get_claim_or_404(session, claim_id)
        if claim.decision is not None and claim.status in (
            "decided",
            "waiting_for_sign_off",
        ):
            return claim_to_detail(session, claim)
        claim.attempts += 1
        existing_steps = list(
            session.scalars(
                select(ClaimStepRecord)
                .where(ClaimStepRecord.claim_id == claim_id)
                .order_by(ClaimStepRecord.step_number)
            )
        )
        next_number = len(existing_steps) + 1
        if claim.attempts < _MAX_ATTEMPTS_BEFORE_HANDLER:
            claim.status = "waiting"
            step_msg = (
                f"Attempt {claim.attempts} failed ({error}); "
                "returned to waiting queue for retry"
            )
        else:
            claim.status = "left_for_handler"
            step_msg = (
                f"Attempt {claim.attempts} failed ({error}); "
                "left for a handler after two failed attempts"
            )
        session.add(
            ClaimStepRecord(
                claim_id=claim_id,
                step_number=next_number,
                message=step_msg,
                created_at=datetime.now(UTC).isoformat(),
            )
        )
        todo = session.scalar(
            select(TodoItemRecord).where(TodoItemRecord.claim_id == claim_id)
        )
        if todo is not None:
            todo.status = (
                "to_do"
                if claim.attempts < _MAX_ATTEMPTS_BEFORE_HANDLER
                else "left_for_handler"
            )
            todo.result_summary = step_msg
        session.commit()
        return claim_to_detail(session, claim)


def sign_off_claim_payout(
    session: Session, claim_id: str, handler_id: str
) -> ClaimDetail:
    """Record a handler's sign-off on an over-limit approval and release payment."""
    with _WRITE_LOCK:
        claim = get_claim_or_404(session, claim_id)
        handler = session.scalar(
            select(HandlerRecord).where(HandlerRecord.handler_id == handler_id)
        )
        if handler is None or not handler.can_approve_over_limit:
            raise HTTPException(
                status_code=404, detail=f"Authorized handler {handler_id} not found"
            )
        if claim.status != "waiting_for_sign_off" or claim.decision != "approve":
            raise HTTPException(
                status_code=409,
                detail="Claim is not awaiting handler sign-off.",
            )
        claim.signed_off_by = handler.handler_id
        claim.payment_status = "paid"
        claim.amount_paid = float(claim.payout or 0.0)
        claim.status = "decided"
        session.commit()
        return claim_to_detail(session, claim)


def get_todos(session: Session) -> list[TodoItemSchema]:
    """Return the current queue run's to-do list in item order."""
    rows = session.scalars(select(TodoItemRecord).order_by(TodoItemRecord.item_order))
    return [
        TodoItemSchema(
            claim_id=row.claim_id,
            description=row.description,
            status=_VALID_TODO_STATUSES.get(row.status, "to_do"),
            result_summary=row.result_summary,
        )
        for row in rows
    ]


def save_todos(session: Session, todos: list[TodoItemSchema]) -> list[TodoItemSchema]:
    """Replace the stored to-do list with the provided items in order."""
    with _WRITE_LOCK:
        session.execute(delete(TodoItemRecord))
        for idx, item in enumerate(todos):
            session.add(
                TodoItemRecord(
                    item_order=idx,
                    claim_id=item.claim_id,
                    description=item.description,
                    status=item.status,
                    result_summary=item.result_summary,
                )
            )
        session.commit()
        return get_todos(session)


def update_single_todo(
    session: Session,
    claim_id: str,
    status: TodoStatus,
    result_summary: str,
    description: str = "",
) -> TodoItemSchema:
    """Update or insert a single claim's to-do item atomically."""
    with _WRITE_LOCK:
        todo = session.scalar(
            select(TodoItemRecord).where(TodoItemRecord.claim_id == claim_id)
        )
        if todo is not None:
            todo.status = status
            todo.result_summary = result_summary
            if description:
                todo.description = description
        else:
            existing = list(session.scalars(select(TodoItemRecord)))
            todo = TodoItemRecord(
                item_order=len(existing),
                claim_id=claim_id,
                description=description or f"Decide claim {claim_id}",
                status=status,
                result_summary=result_summary,
            )
            session.add(todo)
        session.commit()
        return TodoItemSchema(
            claim_id=todo.claim_id,
            description=todo.description,
            status=status,
            result_summary=todo.result_summary,
        )


def get_queue_run_status(session: Session) -> QueueRunStatusResponse:
    """Return the current queue run state, cap, summary, and to-do list."""
    run_rec = session.scalar(select(QueueRunRecord).where(QueueRunRecord.id == 1))
    if run_rec is None:
        return QueueRunStatusResponse(
            status="idle",
            cap=25,
            summary="",
            target_claims=[],
            todos=get_todos(session),
        )
    return QueueRunStatusResponse(
        status=run_rec.status,
        cap=run_rec.cap,
        summary=run_rec.summary,
        target_claims=json.loads(run_rec.target_claims_json or "[]"),
        todos=get_todos(session),
    )


def set_queue_run_state(
    session: Session,
    status: str,
    cap: int,
    summary: str,
    target_claims: list[str] | None = None,
) -> QueueRunStatusResponse:
    """Update the stored queue run status, cap, summary, and target claims."""
    with _WRITE_LOCK:
        run_rec = session.scalar(select(QueueRunRecord).where(QueueRunRecord.id == 1))
        if run_rec is None:
            run_rec = QueueRunRecord(
                id=1,
                status=status,
                cap=cap,
                summary=summary,
                target_claims_json=json.dumps(target_claims or []),
            )
            session.add(run_rec)
        else:
            run_rec.status = status
            run_rec.cap = cap
            run_rec.summary = summary
            if target_claims is not None:
                run_rec.target_claims_json = json.dumps(target_claims)
        session.commit()
        return get_queue_run_status(session)


if __name__ == "__main__":  # pragma: no cover
    reset_db()
