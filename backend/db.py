"""SQLAlchemy database engine, session management, seed loader, and ORM operations."""

import json
import os
import threading
from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from sqlalchemy import Engine, create_engine, delete, select
from sqlalchemy.orm import Session

from backend.models import (
    AddOnRecord,
    Base,
    ClaimRecord,
    ClaimStepRecord,
    CompanyRecord,
    CustomerRecord,
    HandlerRecord,
    InstructionsRecord,
    PlanRecord,
    PolicyRecord,
    PolicyWordingRecord,
)
from backend.schemas import (
    AddOnDetails,
    AddressDetails,
    ClaimDetail,
    ClaimDocument,
    ClaimItem,
    ClaimStep,
    ClaimSummary,
    CustomerDetail,
    DecisionRequest,
    HandlerDetail,
    InstructionsResponse,
    PlanDetails,
    PolicyDetail,
    PolicyWordingResponse,
    PreviousClaim,
    TripDetails,
)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "undercover.db"
POLICY_WORDING_FILE = "policy_wording_short_optimized.md"
FULL_POLICY_WORDING_FILE = "policy_wording_optimized.md"
SHORT_POLICY_WORDING_FILE = "policy_wording_short_optimized.md"

DEFAULT_INSTRUCTIONS = "\n".join(
    [
        "You are the UnderCover Agent, a travel insurance claims handler at "
        "UnderCover Travel Insurance.",
        "",
        "For every claim you handle:",
        "1. First call `get_claim(claim_id)`. Second, call `get_policy(policy_id)` "
        "and `get_policy_wording()` together in one turn (do not call "
        "`check_backend` or `get_customer`).",
        "2. Decide `approve`, `decline`, or `refer` strictly according to the "
        "Policy Wording (Version 2026.1):",
        "   - **Approve:** Covered incident, required supporting documents named in "
        "that section attached (for Section 5, only the incident report for theft, "
        "carrier loss/damage, or accidental damage is required). Compute `Payout = "
        "min(Benefit Max, (Sum of capped eligible items) - (Third-party payments) "
        "- (Deductible))`:",
        "     (1) Sum eligible covered items (exclude consequential loss items). "
        "For Section 5, the per-item limit ($150/$300/$500) applies to each "
        "individual item (for a line with multiple units, check unit price "
        "`amount / quantity` against the limit; a pair or set, such as a pair of "
        "shoes, a suit or a camera with its lens, counts as one item even across "
        "separate lines). Apply $1,200 `Electronics Plus` ONLY when "
        "`electronics_plus` is on the policy and ONLY to phones, tablets, laptops, "
        "cameras and their lenses, e-readers and smartwatches (other items use the "
        "standard limit). **Do NOT cap at Benefit Max in Step 1.**",
        "     (2) Subtract carrier, supplier, or third-party payments/credits.",
        "     (3) Subtract deductible ($100/$50/$0) once ONLY for Section 5 "
        "(Baggage) and Section 7 (Emergency Medical)—$0 for all other sections.",
        "     (4) Cap at Benefit Max (or lower of trip cost and max for Section 2).",
        "   - **Decline (`payout=0.0`):** Reason not covered, waiting period not "
        "met, or an exclusion applies (unattended belongings in public or in a "
        "vehicle outside a locked trunk/glove box, cash >$100, wear and tear, "
        "moths/vermin/insects/pets, data/writing/work value, pre-existing "
        "conditions within 60 days before purchase unless `pre_existing_waiver` "
        "applies, adventure sports unless `adventure_sports` applies, non-urgent "
        "care, or losses while breaking the law or impaired by alcohol or drugs).",
        "   - **Refer (`payout=0.0`):** A required document named in the section "
        "is missing, a Section 3 carrier document's own text states only times and "
        "omits the delay cause (do not rely on the customer's story for carrier "
        "cause confirmation), or attached receipts/documents and the story disagree "
        "on dates or location (always refer under Section 11, never decline under "
        "Section 4, when receipt dates or locations disagree with the story).",
        "3. Call `decide_claim` on every claim. If the `payout` passed to "
        "`decide_claim` differs from the final payout in your `reason`, call "
        "`decide_claim` again with the exact payout from `reason`. When approving "
        "(`payout > 0`), also call `pay_claim` with that payout.",
    ]
)

_ENGINES: dict[str, Engine] = {}
_INIT_LOCK = threading.Lock()
_WRITE_LOCK = threading.RLock()


def get_db_path() -> Path:
    """Return the configured SQLite database file path."""
    return Path(os.getenv("UNDERCOVER_DB_PATH", str(DEFAULT_DB_PATH)))


def get_engine() -> Engine:
    """Return a cached SQLAlchemy engine for the current database path."""
    db_path = get_db_path().resolve()
    url = f"sqlite:///{db_path}"
    if url not in _ENGINES:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        _ENGINES[url] = create_engine(
            url, connect_args={"check_same_thread": False, "timeout": 30}
        )
    return _ENGINES[url]


def _read_json(filename: str) -> Any:
    """Read and parse a JSON file from the data directory."""
    return json.loads((DATA_DIR / filename).read_text(encoding="utf-8"))


def _seed_company_and_docs(session: Session) -> None:
    """Seed company settings, policy wording, and agent instructions."""
    company_data = _read_json("company.json")
    session.add(
        CompanyRecord(
            id=1,
            name=company_data["name"],
            currency=company_data["currency"],
            payout_approval_limit=float(company_data["payout_approval_limit"]),
            claim_filing_window_days=int(company_data["claim_filing_window_days"]),
            pre_existing_look_back_days=int(
                company_data["pre_existing_look_back_days"]
            ),
            policy_wording_version=company_data["policy_wording_version"],
            claims_manual_version=company_data["claims_manual_version"],
            raw_json=json.dumps(company_data),
        )
    )
    wording_text = (DATA_DIR / POLICY_WORDING_FILE).read_text(encoding="utf-8")
    session.add(
        PolicyWordingRecord(
            version=company_data["policy_wording_version"],
            content=wording_text,
        )
    )
    session.add(InstructionsRecord(id=1, instructions=DEFAULT_INSTRUCTIONS))


def _seed_plans_and_add_ons(session: Session) -> None:
    """Seed insurance plans and add-ons from plans.json."""
    plans_data = _read_json("plans.json")
    deductible_applies_to = json.dumps(plans_data["deductible_applies_to"])
    for plan in plans_data["plans"]:
        session.add(
            PlanRecord(
                plan=plan["plan"],
                name=plan["name"],
                trip_cancellation_max=float(plan["trip_cancellation_max"]),
                trip_delay_waiting_hours=int(plan["trip_delay_waiting_hours"]),
                trip_delay_max=float(plan["trip_delay_max"]),
                baggage_delay_waiting_hours=int(plan["baggage_delay_waiting_hours"]),
                baggage_delay_max=float(plan["baggage_delay_max"]),
                baggage_max=float(plan["baggage_max"]),
                per_item_limit=float(plan["per_item_limit"]),
                passport_max=float(plan["passport_max"]),
                emergency_medical_max=float(plan["emergency_medical_max"]),
                deductible=float(plan["deductible"]),
                deductible_applies_to_json=deductible_applies_to,
            )
        )
    for add_on in plans_data["add_ons"]:
        limit = add_on.get("electronics_per_item_limit")
        session.add(
            AddOnRecord(
                add_on=add_on["add_on"],
                name=add_on["name"],
                effect=add_on["effect"],
                electronics_per_item_limit=float(limit) if limit is not None else None,
            )
        )


def _seed_policies_customers_handlers(session: Session) -> None:
    """Seed policies, customers, and claims handlers."""
    for pol in _read_json("policies.json"):
        session.add(
            PolicyRecord(
                policy_id=pol["policy_id"],
                customer_id=pol["customer_id"],
                plan=pol["plan"],
                add_ons_json=json.dumps(pol["add_ons"]),
                purchased_on=pol["purchased_on"],
                sold_through=pol["sold_through"],
                trip_json=json.dumps(pol["trip"]),
                travelers_json=json.dumps(pol["travelers"]),
                status=pol["status"],
            )
        )
    for cus in _read_json("customers.json"):
        session.add(
            CustomerRecord(
                customer_id=cus["customer_id"],
                name=cus["name"],
                email=cus["email"],
                phone=cus["phone"],
                date_of_birth=cus["date_of_birth"],
                address_json=json.dumps(cus["address"]),
                customer_since=cus["customer_since"],
                previous_claims_json=json.dumps(cus["previous_claims"]),
            )
        )
    for hnd in _read_json("handlers.json"):
        session.add(
            HandlerRecord(
                handler_id=hnd["handler_id"],
                name=hnd["name"],
                role=hnd["role"],
                email=hnd["email"],
                can_approve_over_limit=bool(hnd["can_approve_over_limit"]),
            )
        )


def _seed_claims(session: Session) -> None:
    """Seed the 25 queue claims in waiting state."""
    for index, clm in enumerate(_read_json("claims.json")):
        session.add(
            ClaimRecord(
                claim_id=clm["claim_id"],
                queue_order=index,
                policy_id=clm["policy_id"],
                customer_id=clm["customer_id"],
                claim_type=clm["claim_type"],
                submitted_on=clm["submitted_on"],
                incident_date=clm["incident_date"],
                incident_location=clm["incident_location"],
                summary=clm["summary"],
                story=clm["story"],
                items_json=json.dumps(clm["items"]),
                amount_claimed=float(clm["amount_claimed"]),
                documents_json=json.dumps(clm["documents"]),
                status="waiting",
                decision=None,
                payout=None,
                policy_section=None,
                reason=None,
                payment_status="unpaid",
                amount_paid=0.0,
                signed_off_by=None,
            )
        )


def init_db(engine: Engine | None = None) -> None:
    """Create database tables and seed initial operational data if empty."""
    target_engine = engine or get_engine()
    with _INIT_LOCK:
        Base.metadata.create_all(target_engine)
        with Session(target_engine) as session:
            existing = session.scalar(
                select(CompanyRecord).where(CompanyRecord.id == 1)
            )
            if existing is not None:
                return
            _seed_company_and_docs(session)
            _seed_plans_and_add_ons(session)
            _seed_policies_customers_handlers(session)
            _seed_claims(session)
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
    """Reset all claims and steps back to their initial waiting state."""
    with _WRITE_LOCK:
        session.execute(delete(ClaimStepRecord))
        for claim in session.scalars(select(ClaimRecord)):
            claim.status = "waiting"
            claim.decision = None
            claim.payout = None
            claim.policy_section = None
            claim.reason = None
            claim.payment_status = "unpaid"
            claim.amount_paid = 0.0
            claim.signed_off_by = None
        session.commit()
        return list_claims(session)


def update_instructions_if_default(session: Session) -> None:
    """Keep the stored default instructions and policy wording current."""
    changed = False
    record = session.scalar(
        select(InstructionsRecord).where(InstructionsRecord.id == 1)
    )
    if record is not None and record.instructions != DEFAULT_INSTRUCTIONS:
        record.instructions = DEFAULT_INSTRUCTIONS
        changed = True
    wording = session.scalar(select(PolicyWordingRecord))
    latest_wording = (DATA_DIR / POLICY_WORDING_FILE).read_text(encoding="utf-8")
    if wording is not None and wording.content != latest_wording:
        wording.content = latest_wording
        changed = True
    if changed:
        session.commit()


def claim_to_summary(row: ClaimRecord) -> ClaimSummary:
    """Convert a ClaimRecord ORM row into a ClaimSummary schema."""
    return ClaimSummary(
        claim_id=row.claim_id,
        policy_id=row.policy_id,
        customer_id=row.customer_id,
        claim_type=row.claim_type,
        submitted_on=row.submitted_on,
        incident_date=row.incident_date,
        incident_location=row.incident_location,
        summary=row.summary,
        amount_claimed=row.amount_claimed,
        status=row.status,
        decision=row.decision,
        payout=row.payout,
        policy_section=row.policy_section,
        reason=row.reason,
        payment_status=row.payment_status,
        amount_paid=row.amount_paid,
        signed_off_by=row.signed_off_by,
    )


def claim_to_detail(session: Session, row: ClaimRecord) -> ClaimDetail:
    """Convert a ClaimRecord ORM row and its steps into a ClaimDetail schema."""
    steps = list(
        session.scalars(
            select(ClaimStepRecord)
            .where(ClaimStepRecord.claim_id == row.claim_id)
            .order_by(ClaimStepRecord.step_number)
        )
    )
    items = [ClaimItem.model_validate(item) for item in json.loads(row.items_json)]
    documents = [
        ClaimDocument.model_validate(doc) for doc in json.loads(row.documents_json)
    ]
    step_models = [
        ClaimStep(
            step_number=s.step_number,
            message=s.message,
            created_at=s.created_at,
        )
        for s in steps
    ]
    return ClaimDetail(
        **claim_to_summary(row).model_dump(),
        story=row.story,
        items=items,
        documents=documents,
        steps=step_models,
    )


def get_claim_or_404(session: Session, claim_id: str) -> ClaimRecord:
    """Fetch a claim by ID or raise HTTP 404."""
    claim = session.scalar(select(ClaimRecord).where(ClaimRecord.claim_id == claim_id))
    if claim is None:
        raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")
    return claim


def list_claims(session: Session) -> list[ClaimSummary]:
    """Return all claims ordered by their queue position."""
    rows = session.scalars(select(ClaimRecord).order_by(ClaimRecord.queue_order))
    return [claim_to_summary(row) for row in rows]


def get_claim_detail(session: Session, claim_id: str) -> ClaimDetail:
    """Return the full detail for a single claim."""
    claim = get_claim_or_404(session, claim_id)
    return claim_to_detail(session, claim)


def get_policy_detail(session: Session, policy_id: str) -> PolicyDetail:
    """Return a policy along with its resolved plan and add-on details."""
    policy = session.scalar(
        select(PolicyRecord).where(PolicyRecord.policy_id == policy_id)
    )
    if policy is None:
        raise HTTPException(status_code=404, detail=f"Policy {policy_id} not found")
    plan = session.scalar(select(PlanRecord).where(PlanRecord.plan == policy.plan))
    if plan is None:
        raise HTTPException(status_code=404, detail=f"Plan {policy.plan} not found")
    add_on_ids: list[str] = json.loads(policy.add_ons_json)
    add_on_details: list[AddOnDetails] = []
    for add_on_id in add_on_ids:
        add_on = session.scalar(
            select(AddOnRecord).where(AddOnRecord.add_on == add_on_id)
        )
        if add_on is not None:
            add_on_details.append(
                AddOnDetails(
                    add_on=add_on.add_on,
                    name=add_on.name,
                    effect=add_on.effect,
                    electronics_per_item_limit=add_on.electronics_per_item_limit,
                )
            )
    plan_details = PlanDetails(
        plan=plan.plan,
        name=plan.name,
        trip_cancellation_max=plan.trip_cancellation_max,
        trip_delay_waiting_hours=plan.trip_delay_waiting_hours,
        trip_delay_max=plan.trip_delay_max,
        baggage_delay_waiting_hours=plan.baggage_delay_waiting_hours,
        baggage_delay_max=plan.baggage_delay_max,
        baggage_max=plan.baggage_max,
        per_item_limit=plan.per_item_limit,
        passport_max=plan.passport_max,
        emergency_medical_max=plan.emergency_medical_max,
        deductible=plan.deductible,
        deductible_applies_to=json.loads(plan.deductible_applies_to_json),
    )
    return PolicyDetail(
        policy_id=policy.policy_id,
        customer_id=policy.customer_id,
        plan=policy.plan,
        add_ons=add_on_ids,
        purchased_on=policy.purchased_on,
        sold_through=policy.sold_through,
        trip=TripDetails.model_validate(json.loads(policy.trip_json)),
        travelers=json.loads(policy.travelers_json),
        status=policy.status,
        plan_details=plan_details,
        add_on_details=add_on_details,
    )


def get_customer_detail(session: Session, customer_id: str) -> CustomerDetail:
    """Return a customer profile and prior claim history."""
    customer = session.scalar(
        select(CustomerRecord).where(CustomerRecord.customer_id == customer_id)
    )
    if customer is None:
        raise HTTPException(status_code=404, detail=f"Customer {customer_id} not found")
    return CustomerDetail(
        customer_id=customer.customer_id,
        name=customer.name,
        email=customer.email,
        phone=customer.phone,
        date_of_birth=customer.date_of_birth,
        address=AddressDetails.model_validate(json.loads(customer.address_json)),
        customer_since=customer.customer_since,
        previous_claims=[
            PreviousClaim.model_validate(c)
            for c in json.loads(customer.previous_claims_json)
        ],
    )


def list_handlers(session: Session) -> list[HandlerDetail]:
    """Return all claims handlers ordered by handler ID."""
    rows = session.scalars(select(HandlerRecord).order_by(HandlerRecord.handler_id))
    return [
        HandlerDetail(
            handler_id=row.handler_id,
            name=row.name,
            role=row.role,
            email=row.email,
            can_approve_over_limit=row.can_approve_over_limit,
        )
        for row in rows
    ]


def get_policy_wording_doc(session: Session) -> PolicyWordingResponse:
    """Return the active contractual policy wording."""
    update_instructions_if_default(session)
    wording = session.scalar(select(PolicyWordingRecord))
    if wording is None:
        raise HTTPException(status_code=404, detail="Policy wording not found")
    return PolicyWordingResponse(version=wording.version, content=wording.content)


def get_instructions_doc(session: Session) -> InstructionsResponse:
    """Return the read-only system prompt for the UnderCover Agent."""
    update_instructions_if_default(session)
    record = session.scalar(
        select(InstructionsRecord).where(InstructionsRecord.id == 1)
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Instructions not found")
    return InstructionsResponse(instructions=record.instructions)


def get_approval_limit(session: Session) -> float:
    """Return the payout threshold above which handler sign-off is required."""
    company = session.scalar(select(CompanyRecord).where(CompanyRecord.id == 1))
    return company.payout_approval_limit if company is not None else 1000.0


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
    """Record the agent's decision on a claim and apply the $1,000 sign-off rule."""
    with _WRITE_LOCK:
        claim = get_claim_or_404(session, claim_id)
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
    """Pay an approved claim if within limit or already signed off by a handler."""
    with _WRITE_LOCK:
        claim = get_claim_or_404(session, claim_id)
        limit = get_approval_limit(session)
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


if __name__ == "__main__":  # pragma: no cover
    reset_db()
