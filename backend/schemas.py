"""Pydantic schemas for UnderCover API requests and responses."""

from typing import Literal

from pydantic import BaseModel


class ClaimItem(BaseModel):
    """Single expense item claimed by the customer."""

    description: str
    category: str
    amount: float


class ClaimDocument(BaseModel):
    """Supporting text document attached to a claim."""

    name: str
    type: str
    content: str


class ClaimStep(BaseModel):
    """Single step logged while the agent works on a claim."""

    step_number: int
    message: str
    created_at: str


class ClaimSummary(BaseModel):
    """Summary representation of a claim in the queue."""

    claim_id: str
    policy_id: str
    customer_id: str
    claim_type: str
    submitted_on: str
    incident_date: str
    incident_location: str
    summary: str
    amount_claimed: float
    status: str
    decision: str | None
    payout: float | None
    policy_section: str | None
    reason: str | None
    payment_status: str
    amount_paid: float
    signed_off_by: str | None


class ClaimDetail(ClaimSummary):
    """Full claim record with customer story, items, documents, and agent steps."""

    story: str
    items: list[ClaimItem]
    documents: list[ClaimDocument]
    steps: list[ClaimStep]


class PlanDetails(BaseModel):
    """Benefit limits, waiting periods, and deductible for a policy plan."""

    plan: str
    name: str
    trip_cancellation_max: float
    trip_delay_waiting_hours: int
    trip_delay_max: float
    baggage_delay_waiting_hours: int
    baggage_delay_max: float
    baggage_max: float
    per_item_limit: float
    passport_max: float
    emergency_medical_max: float
    deductible: float
    deductible_applies_to: list[str]


class AddOnDetails(BaseModel):
    """Optional coverage add-on details."""

    add_on: str
    name: str
    effect: str
    electronics_per_item_limit: float | None


class TripDetails(BaseModel):
    """Covered trip destination, dates, and cost."""

    destination: str
    departs_on: str
    returns_on: str
    trip_cost: float


class PolicyDetail(BaseModel):
    """Policy record resolved with its plan and add-on details."""

    policy_id: str
    customer_id: str
    plan: str
    add_ons: list[str]
    purchased_on: str
    sold_through: str
    trip: TripDetails
    travelers: list[str]
    status: str
    plan_details: PlanDetails
    add_on_details: list[AddOnDetails]


class AddressDetails(BaseModel):
    """Customer mailing address."""

    street: str
    city: str
    state: str
    zip: str


class PreviousClaim(BaseModel):
    """Summary of an earlier claim filed by a customer."""

    claim_id: str
    filed_on: str
    incident_date: str
    claim_type: str
    summary: str
    outcome: str
    amount_paid: float


class CustomerDetail(BaseModel):
    """Customer contact details and claim history."""

    customer_id: str
    name: str
    email: str
    phone: str
    date_of_birth: str
    address: AddressDetails
    customer_since: str
    previous_claims: list[PreviousClaim]


class HandlerDetail(BaseModel):
    """Claims handler profile."""

    handler_id: str
    name: str
    role: str
    email: str
    can_approve_over_limit: bool


class PolicyWordingResponse(BaseModel):
    """Contractual policy wording document."""

    version: str
    content: str


class InstructionsResponse(BaseModel):
    """Read-only system prompt for the UnderCover Agent."""

    instructions: str


class StepRequest(BaseModel):
    """Request body for recording an agent progress step."""

    message: str


class DecisionRequest(BaseModel):
    """Request body for recording a claim decision."""

    decision: Literal["approve", "decline", "refer"]
    payout: float
    policy_section: str
    reason: str


class PayRequest(BaseModel):
    """Request body for paying an approved claim."""

    amount: float


class SignOffRequest(BaseModel):
    """Request body for handler sign-off on payouts over $1,000."""

    handler_id: str
