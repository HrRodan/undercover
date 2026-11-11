"""Read-only ORM entity queries and schema serializers for the UnderCover backend."""

import json

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from agent.config import get_agent_config
from backend.config import get_backend_config
from backend.models import (
    AddOnRecord,
    ClaimRecord,
    ClaimStepRecord,
    CompanyRecord,
    CustomerRecord,
    HandlerRecord,
    PlanRecord,
    PolicyRecord,
)
from backend.schemas import (
    AddOnDetails,
    AddressDetails,
    ClaimDetail,
    ClaimDocument,
    ClaimItem,
    ClaimStep,
    ClaimSummary,
    ConfigResponse,
    CustomerDetail,
    HandlerDetail,
    PlanDetails,
    PolicyDetail,
    PreviousClaim,
    TripDetails,
)


def get_config_response() -> ConfigResponse:
    """Return the active file and model configuration."""
    b_cfg = get_backend_config()
    a_cfg = get_agent_config()
    return ConfigResponse(
        policy_wording_file=b_cfg.policy_wording_file,
        claims_manual_file=b_cfg.claims_manual_file,
        claims_file=b_cfg.claims_file,
        policies_file=b_cfg.policies_file,
        customers_file=b_cfg.customers_file,
        plans_file=b_cfg.plans_file,
        handlers_file=b_cfg.handlers_file,
        company_file=b_cfg.company_file,
        default_model=a_cfg.default_model,
        queue_model_name=a_cfg.queue_model_name,
        claim_model_name=a_cfg.claim_model_name,
        queue_reasoning_effort=a_cfg.queue_reasoning_effort,
        claim_reasoning_effort=a_cfg.claim_reasoning_effort,
    )


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
        attempts=row.attempts,
        sections_read=json.loads(row.sections_read_json or "[]"),
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


def get_approval_limit(session: Session) -> float:
    """Return the payout threshold above which handler sign-off is required."""
    company = session.scalar(select(CompanyRecord).where(CompanyRecord.id == 1))
    return company.payout_approval_limit if company is not None else 1000.0
