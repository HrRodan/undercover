"""SQLAlchemy 2.x ORM models for the UnderCover backend."""

from sqlalchemy import Boolean, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all UnderCover ORM models."""


class CompanyRecord(Base):
    """Company configuration and approval thresholds."""

    __tablename__ = "company"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    currency: Mapped[str] = mapped_column(String(16))
    payout_approval_limit: Mapped[float] = mapped_column(Float)
    claim_filing_window_days: Mapped[int] = mapped_column(Integer)
    pre_existing_look_back_days: Mapped[int] = mapped_column(Integer)
    policy_wording_version: Mapped[str] = mapped_column(String(32))
    claims_manual_version: Mapped[str] = mapped_column(String(32))
    raw_json: Mapped[str] = mapped_column(Text)


class PlanRecord(Base):
    """Insurance plan tier and benefit limits."""

    __tablename__ = "plans"

    plan: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    trip_cancellation_max: Mapped[float] = mapped_column(Float)
    trip_delay_waiting_hours: Mapped[int] = mapped_column(Integer)
    trip_delay_max: Mapped[float] = mapped_column(Float)
    baggage_delay_waiting_hours: Mapped[int] = mapped_column(Integer)
    baggage_delay_max: Mapped[float] = mapped_column(Float)
    baggage_max: Mapped[float] = mapped_column(Float)
    per_item_limit: Mapped[float] = mapped_column(Float)
    passport_max: Mapped[float] = mapped_column(Float)
    emergency_medical_max: Mapped[float] = mapped_column(Float)
    deductible: Mapped[float] = mapped_column(Float)
    deductible_applies_to_json: Mapped[str] = mapped_column(Text)


class AddOnRecord(Base):
    """Optional policy add-on coverage."""

    __tablename__ = "add_ons"

    add_on: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    effect: Mapped[str] = mapped_column(Text)
    electronics_per_item_limit: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )


class PolicyRecord(Base):
    """Customer travel insurance policy record."""

    __tablename__ = "policies"

    policy_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    customer_id: Mapped[str] = mapped_column(String(64), index=True)
    plan: Mapped[str] = mapped_column(String(64))
    add_ons_json: Mapped[str] = mapped_column(Text)
    purchased_on: Mapped[str] = mapped_column(String(32))
    sold_through: Mapped[str] = mapped_column(String(200))
    trip_json: Mapped[str] = mapped_column(Text)
    travelers_json: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32))


class CustomerRecord(Base):
    """Insured customer record and prior claim history."""

    __tablename__ = "customers"

    customer_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(200))
    phone: Mapped[str] = mapped_column(String(64))
    date_of_birth: Mapped[str] = mapped_column(String(32))
    address_json: Mapped[str] = mapped_column(Text)
    customer_since: Mapped[str] = mapped_column(String(32))
    previous_claims_json: Mapped[str] = mapped_column(Text)


class HandlerRecord(Base):
    """Claims handler profile."""

    __tablename__ = "handlers"

    handler_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(200))
    can_approve_over_limit: Mapped[bool] = mapped_column(Boolean)


class ClaimRecord(Base):
    """Travel insurance claim in the operational queue."""

    __tablename__ = "claims"

    claim_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    queue_order: Mapped[int] = mapped_column(Integer, index=True)
    policy_id: Mapped[str] = mapped_column(String(64), index=True)
    customer_id: Mapped[str] = mapped_column(String(64), index=True)
    claim_type: Mapped[str] = mapped_column(String(64))
    submitted_on: Mapped[str] = mapped_column(String(32))
    incident_date: Mapped[str] = mapped_column(String(32))
    incident_location: Mapped[str] = mapped_column(String(200))
    summary: Mapped[str] = mapped_column(Text)
    story: Mapped[str] = mapped_column(Text)
    items_json: Mapped[str] = mapped_column(Text)
    amount_claimed: Mapped[float] = mapped_column(Float)
    documents_json: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(64), default="waiting")
    decision: Mapped[str | None] = mapped_column(String(32), nullable=True)
    payout: Mapped[float | None] = mapped_column(Float, nullable=True)
    policy_section: Mapped[str | None] = mapped_column(String(200), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    payment_status: Mapped[str] = mapped_column(String(64), default="unpaid")
    amount_paid: Mapped[float] = mapped_column(Float, default=0.0)
    signed_off_by: Mapped[str | None] = mapped_column(String(64), nullable=True)


class ClaimStepRecord(Base):
    """Step-by-step log entry recorded while the agent processes a claim."""

    __tablename__ = "claim_steps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    claim_id: Mapped[str] = mapped_column(String(64), index=True)
    step_number: Mapped[int] = mapped_column(Integer)
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(64))


class PolicyWordingRecord(Base):
    """Contractual policy wording text."""

    __tablename__ = "policy_wording"

    version: Mapped[str] = mapped_column(String(32), primary_key=True)
    content: Mapped[str] = mapped_column(Text)


class InstructionsRecord(Base):
    """Read-only system instructions for the UnderCover Agent."""

    __tablename__ = "instructions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    instructions: Mapped[str] = mapped_column(Text)
