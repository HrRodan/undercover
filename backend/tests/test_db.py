"""Unit tests for the SQLAlchemy database models and seed data layer."""

from pathlib import Path

import pytest
from sqlalchemy import func, select

from backend import db, schemas
from backend.models import (
    AddOnRecord,
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


def test_seed_counts_and_initial_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify seeding loads exact record counts and initializes claims to waiting."""
    db_file = tmp_path / "test_undercover.db"
    monkeypatch.setenv("UNDERCOVER_DB_PATH", str(db_file))

    session_gen = db.get_session()
    session = next(session_gen)
    try:
        claims = list(
            session.scalars(select(ClaimRecord).order_by(ClaimRecord.queue_order))
        )
        assert len(claims) == 25
        assert claims[0].claim_id == "CLM-1001"
        assert claims[-1].claim_id == "CLM-1025"
        for claim in claims:
            assert claim.status == "waiting"
            assert claim.payment_status == "unpaid"
            assert claim.amount_paid == 0.0
            assert claim.decision is None
            assert claim.payout is None
            assert claim.signed_off_by is None

        step_count = session.scalar(select(func.count()).select_from(ClaimStepRecord))
        assert step_count == 0

        policy_count = session.scalar(select(func.count()).select_from(PolicyRecord))
        assert policy_count == 50

        customer_count = session.scalar(
            select(func.count()).select_from(CustomerRecord)
        )
        assert customer_count == 49

        plan_count = session.scalar(select(func.count()).select_from(PlanRecord))
        assert plan_count == 3

        add_on_count = session.scalar(select(func.count()).select_from(AddOnRecord))
        assert add_on_count == 3

        handler_count = session.scalar(select(func.count()).select_from(HandlerRecord))
        assert handler_count == 3

        company = session.scalar(select(CompanyRecord).where(CompanyRecord.id == 1))
        assert company is not None
        assert company.payout_approval_limit == 1000.0
        assert company.currency == "USD"

        wording = session.scalar(
            select(PolicyWordingRecord).where(PolicyWordingRecord.version == "2026.1")
        )
        assert wording is not None
        assert "# UnderCover Travel Insurance: Policy Wording" in wording.content

        instructions = session.scalar(
            select(InstructionsRecord).where(InstructionsRecord.id == 1)
        )
        assert instructions is not None
        assert "UnderCover Agent" in instructions.instructions
    finally:
        session_gen.close()


def test_init_db_is_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify calling init_db repeatedly does not duplicate rows."""
    db_file = tmp_path / "idempotent.db"
    monkeypatch.setenv("UNDERCOVER_DB_PATH", str(db_file))

    db.init_db()
    db.init_db()
    db.reset_db()

    session_gen = db.get_session()
    session = next(session_gen)
    try:
        claim_count = session.scalar(select(func.count()).select_from(ClaimRecord))
        assert claim_count == 25
    finally:
        session_gen.close()


def test_restricted_files_are_never_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify seeding never reads data/evals/, claims_manual.md, or data/security/."""
    db_file = tmp_path / "restricted_check.db"
    monkeypatch.setenv("UNDERCOVER_DB_PATH", str(db_file))

    accessed_paths: list[Path] = []
    original_read_text = Path.read_text

    def tracked_read_text(
        self: Path, encoding: str | None = None, errors: str | None = None
    ) -> str:
        accessed_paths.append(self.resolve())
        return original_read_text(self, encoding=encoding, errors=errors)

    monkeypatch.setattr(Path, "read_text", tracked_read_text)
    db.init_db()

    accessed_names = {p.name for p in accessed_paths}
    accessed_parts = {part for p in accessed_paths for part in p.parts}
    assert "evals" not in accessed_parts
    assert "security" not in accessed_parts
    assert "claims_manual.md" not in accessed_names

    db_source = Path(db.__file__).read_text(encoding="utf-8")
    models_source = Path(db.__file__).with_name("models.py").read_text(encoding="utf-8")
    assert "sqlite3" not in db_source
    assert "sqlite3" not in models_source


def test_schemas_validation() -> None:
    """Verify request and response Pydantic schemas validate required fields."""
    step_req = schemas.StepRequest(message="Reading claim CLM-1001")
    assert step_req.message == "Reading claim CLM-1001"

    decision_req = schemas.DecisionRequest(
        decision="approve",
        payout=420.0,
        policy_section="Section 3: Trip Delay",
        reason="Covered delay.",
    )
    assert decision_req.payout == 420.0

    pay_req = schemas.PayRequest(amount=420.0)
    assert pay_req.amount == 420.0

    sign_off_req = schemas.SignOffRequest(handler_id="HND-01")
    assert sign_off_req.handler_id == "HND-01"
