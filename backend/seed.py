"""Initial database seed loaders and default instructions for the UnderCover backend."""

import json
import threading
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.config import DEFAULT_DATA_DIR, get_backend_config
from backend.models import (
    AddOnRecord,
    ClaimRecord,
    ClaimsManualRecord,
    CompanyRecord,
    CustomerRecord,
    HandlerRecord,
    InstructionsRecord,
    PlanRecord,
    PolicyRecord,
    PolicyWordingRecord,
    QueueRunRecord,
)

DATA_DIR = DEFAULT_DATA_DIR

QUEUE_INSTRUCTIONS = "\n".join(
    [
        "You are the UnderCover Queue Agent, overseeing the claims queue at "
        "UnderCover Travel Insurance.",
        "",
        "Your workflow for running the queue:",
        "1. Call `get_waiting_claims()` to inspect the waiting claims in scope for "
        "this run.",
        "2. Plan your work by calling `write_todos(todos)` with one item per claim "
        "in the order you choose (`status='to_do'`).",
        "3. For each claim, update its to-do status to `in_progress`, delegate it "
        "to a fresh claim helper via `work_claim(claim_id)`, and update the to-do "
        "list as claims complete (`done`) or are escalated (`left_for_handler`).",
        "4. If a claim fails on its first attempt (`returned to waiting queue`), "
        "call `work_claim(claim_id)` one more time to retry it. If a claim fails "
        "twice, leave it as `left_for_handler` and continue.",
        "5. Before finishing, call `check_missed_claims()` to verify that no "
        "waiting claim within the run cap was missed.",
        "6. Finish with a concise handover summary for the claims handlers listing "
        "what was decided, any payouts awaiting handler sign-off (>$1,000), and "
        "any claims left for a handler.",
    ]
)

CLAIM_INSTRUCTIONS = "\n".join(
    [
        "You are the UnderCover Claim Subagent, a travel insurance claims handler "
        "at UnderCover Travel Insurance deciding one claim from a clean start.",
        "",
        "Follow the Policy Wording (Version 2026.1) and the Claims Handling Manual "
        "(Version 2026.2):",
        "1. Call `get_claim(claim_id)`, `get_policy(policy_id)`, and "
        "`get_customer(customer_id)` to inspect the story, items, attached "
        "documents, plan limits, add-ons, trip dates, and prior claim history.",
        "2. Look up the relevant sections of `policy_wording` and `claims_manual` "
        "using `list_document_sections`, `search_documents`, and "
        "`read_document_section(doc_name, section_id)` rather than reading whole "
        "documents at once.",
        "3. Apply both the Policy Wording and the Claims Handling Manual rules:",
        "   - **Repeat claims (Manual Section 9):** If this claim is the customer's "
        "third claim within 12 months (counting prior claims by `filed_on` date "
        "plus this claim's `submitted_on` date), refer to the Special "
        "Investigations Unit (`decision='refer'`, `payout=0.0`).",
        "   - **Story vs. documents conflict (Manual Section 8):** If receipt dates "
        "or locations contradict the story, or carrier reports disagree on dates "
        "or items, refer to Special Investigations (`decision='refer'`, `payout=0.0`).",
        "   - **Required documents (Manual Section 5):** If a required document is "
        "missing (or a Trip Delay carrier report omits the delay cause), refer "
        "with a document request (`decision='refer'`, `payout=0.0`). If the "
        "customer admits a required step was never taken (such as never reporting "
        "a theft to police within 24 hours), decline (`decision='decline'`).",
        "   - **Wild animals (Manual Section 7):** Losses caused by wild animals "
        "(monkeys, gulls, bears, giraffes) are covered as accidental loss/damage "
        "(not theft, no police report required, outside the vermin/pet exclusion) "
        "when supported by a hotel, guide, tour, or park statement. Rats and mice "
        "remain excluded as vermin.",
        "   - **Meals without receipts (Manual Section 10):** For covered Trip "
        "Delay, unreceipted meals are payable at $35 per traveler per 24-hour "
        "period (or part thereof) of delay.",
        "   - **Reasonable accommodation (Manual Section 7):** Trip Delay "
        "accommodation is capped at $350 per night per room (1 room per 2 "
        "travelers). Exclude consequential loss lines and pay covered lines.",
        "   - **Payout calculation (Wording Payment / Manual Section 6):** "
        "`Payout = min(Benefit Max, (Sum of capped eligible items) - "
        "(Third-party payments) - (Deductible))`. Cap each individual item (or "
        "combined pair/set) at the plan per-item limit ($150/$300/$500, or $1,200 "
        "with `electronics_plus` for phones, tablets, laptops, cameras+lenses, "
        "e-readers, smartwatches). Subtract deductible ($100/$50/$0) once ONLY "
        "for Baggage and Emergency Medical ($0 for other benefits). If the net "
        "payout is <= $0, decline.",
        "4. Call `decide_claim(claim_id, decision, payout, policy_section, reason)` "
        "with a 2-3 sentence explanation citing the section. When `decision == "
        "'approve'` and `payout > 0`, also call `pay_claim(claim_id, payout)`.",
        "5. Reply in one concise line with the claim ID, decision, and payout.",
    ]
)

DEFAULT_INSTRUCTIONS = (
    "# Queue Agent Instructions\n\n"
    f"{QUEUE_INSTRUCTIONS}\n\n"
    "# Claim Subagent Instructions\n\n"
    f"{CLAIM_INSTRUCTIONS}"
)


def read_json(filename: str) -> Any:
    """Read and parse a JSON file from the configured data directory."""
    cfg = get_backend_config()
    return json.loads((cfg.data_dir / filename).read_text(encoding="utf-8"))


def read_text(filename: str) -> str:
    """Read a UTF-8 text file from the configured data directory."""
    cfg = get_backend_config()
    return (cfg.data_dir / filename).read_text(encoding="utf-8")


def _seed_company_and_docs(session: Session) -> None:
    """Seed company settings, policy wording, claims manual, and instructions."""
    cfg = get_backend_config()
    company_data = read_json(cfg.company_file)
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
    session.add(
        PolicyWordingRecord(
            version=company_data["policy_wording_version"],
            content=read_text(cfg.policy_wording_file),
        )
    )
    session.add(
        ClaimsManualRecord(
            version=company_data["claims_manual_version"],
            content=read_text(cfg.claims_manual_file),
        )
    )
    session.add(
        InstructionsRecord(
            id=1,
            instructions=DEFAULT_INSTRUCTIONS,
            queue_instructions=QUEUE_INSTRUCTIONS,
            claim_instructions=CLAIM_INSTRUCTIONS,
        )
    )
    session.add(
        QueueRunRecord(
            id=1,
            status="idle",
            cap=25,
            summary="",
            target_claims_json="[]",
        )
    )


def _seed_plans_and_add_ons(session: Session) -> None:
    """Seed insurance plans and add-ons from the configured plans file."""
    cfg = get_backend_config()
    plans_data = read_json(cfg.plans_file)
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
    cfg = get_backend_config()
    for pol in read_json(cfg.policies_file):
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
    for cus in read_json(cfg.customers_file):
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
    for hnd in read_json(cfg.handlers_file):
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
    cfg = get_backend_config()
    for index, clm in enumerate(read_json(cfg.claims_file)):
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
                attempts=0,
                sections_read_json="[]",
            )
        )


def seed_all(session: Session) -> None:
    """Run all initial database seeders within the provided session."""
    _seed_company_and_docs(session)
    _seed_plans_and_add_ons(session)
    _seed_policies_customers_handlers(session)
    _seed_claims(session)


def sync_docs_and_instructions(session: Session, write_lock: threading.RLock) -> None:
    """Keep stored instructions, policy wording, and claims manual synchronized."""
    with write_lock:
        cfg = get_backend_config()
        changed = False
        record = session.scalar(
            select(InstructionsRecord).where(InstructionsRecord.id == 1)
        )
        if record is not None and (
            record.instructions != DEFAULT_INSTRUCTIONS
            or record.queue_instructions != QUEUE_INSTRUCTIONS
            or record.claim_instructions != CLAIM_INSTRUCTIONS
        ):
            record.instructions = DEFAULT_INSTRUCTIONS
            record.queue_instructions = QUEUE_INSTRUCTIONS
            record.claim_instructions = CLAIM_INSTRUCTIONS
            changed = True
        wording = session.scalar(select(PolicyWordingRecord))
        latest_wording = read_text(cfg.policy_wording_file)
        if wording is not None and wording.content != latest_wording:
            wording.content = latest_wording
            changed = True
        manual = session.scalar(select(ClaimsManualRecord))
        latest_manual = read_text(cfg.claims_manual_file)
        if manual is None:
            company = session.scalar(select(CompanyRecord).where(CompanyRecord.id == 1))
            ver = company.claims_manual_version if company is not None else "2026.2"
            session.add(ClaimsManualRecord(version=ver, content=latest_manual))
            changed = True
        elif manual.content != latest_manual:
            manual.content = latest_manual
            changed = True
        if changed:
            session.commit()
