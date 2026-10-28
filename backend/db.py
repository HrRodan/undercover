"""SQLAlchemy database engine, session management, and seed loader."""

import json
import os
from collections.abc import Generator
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, select
from sqlalchemy.orm import Session

from backend.models import (
    AddOnRecord,
    Base,
    ClaimRecord,
    CompanyRecord,
    CustomerRecord,
    HandlerRecord,
    InstructionsRecord,
    PlanRecord,
    PolicyRecord,
    PolicyWordingRecord,
)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "undercover.db"

DEFAULT_INSTRUCTIONS = "\n".join(
    [
        "You are the UnderCover Agent, a travel insurance claims handler at "
        "UnderCover Travel Insurance.",
        "",
        "For every claim you handle:",
        "1. Read the claim with `get_claim`, the customer's policy with `get_policy`, "
        "the customer's profile and prior claims with `get_customer`, and the "
        "contract wording with `get_policy_wording`.",
        "2. Decide whether to `approve`, `decline`, or `refer` the claim strictly "
        "according to the Policy Wording (Version 2026.1):",
        "   - Check that the incident happened during the covered trip dates on the "
        "policy (or during a covered return Trip Delay that extended travel past the "
        "return date) and that the event was not publicly known before the policy "
        "purchase date.",
        "   - Check benefit waiting periods: Trip Delay requires 12 hours (Economy), "
        "6 hours (Premium), or 3 hours (First); Baggage Delay requires 24 hours "
        "(Economy), 12 hours (Premium), or 6 hours (First) and does not apply on the "
        "journey home.",
        "   - Check required supporting documents for the benefit section. If a "
        "required document is missing or the claim requires human judgment, `refer` "
        "the claim with a payout of $0.00.",
        "   - Check exclusions: unattended belongings, cash over $100, wear and tear, "
        "damage by moths/vermin/insects/pets, value of data/information, pre-existing "
        "medical conditions within the 60-day look-back period (unless the "
        "Pre-Existing Condition Waiver add-on applies), adventure sports injuries "
        "(unless the Adventure Sports add-on applies and certification/limits are "
        "met), and treatment that can reasonably wait until home.",
        "3. Work out the payout in US dollars when you approve:",
        "   - Start with the eligible amount of each item or expense. For Baggage and "
        "Personal Effects, cap each item (or pair/set) at the plan's per-item limit "
        "($150 Economy, $300 Premium, $500 First; or $1,200 for electronics with the "
        "Electronics Plus add-on).",
        "   - Subtract any carrier, hotel, supplier, or third-party compensation or "
        "refund first.",
        "   - Subtract the plan deductible ($100 Economy, $50 Premium, $0 First) once "
        "per claim ONLY for Baggage and Personal Effects and Emergency Medical. Do "
        "not apply the deductible to Trip Cancellation/Interruption, Trip Delay, "
        "Baggage Delay, or Passport claims.",
        "   - Cap the payout at the plan's maximum for the benefit (and at the "
        "insured trip cost for Trip Cancellation/Interruption).",
        "4. Record your decision with `decide_claim`, giving the decision (`approve`, "
        "`decline`, or `refer`), the payout in USD (`0.0` when declining or "
        "referring), the relevant policy wording section (for example, `Section 3: "
        "Trip Delay`), and a clear explanation in two or three sentences.",
        "5. When you approve a claim (`payout > 0`), call `pay_claim` with the "
        "approved payout amount. Payouts over $1,000 require a handler's sign-off and "
        "will be held pending sign-off by the backend.",
    ]
)

_ENGINES: dict[str, Engine] = {}


def get_db_path() -> Path:
    """Return the configured SQLite database file path."""
    return Path(os.getenv("UNDERCOVER_DB_PATH", str(DEFAULT_DB_PATH)))


def get_engine() -> Engine:
    """Return a cached SQLAlchemy engine for the current database path."""
    db_path = get_db_path().resolve()
    url = f"sqlite:///{db_path}"
    if url not in _ENGINES:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        _ENGINES[url] = create_engine(url, connect_args={"check_same_thread": False})
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
    wording_text = (DATA_DIR / "policy_wording.md").read_text(encoding="utf-8")
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
    Base.metadata.create_all(target_engine)
    with Session(target_engine) as session:
        existing = session.scalar(select(CompanyRecord).where(CompanyRecord.id == 1))
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
