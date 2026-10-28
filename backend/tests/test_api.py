"""API tests for the UnderCover backend."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture
def api_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Return a TestClient configured against an isolated SQLite database."""
    monkeypatch.setenv("UNDERCOVER_DB_PATH", str(tmp_path / "api_test.db"))
    return TestClient(app)


def test_read_endpoints(api_client: TestClient) -> None:
    """Verify read endpoints for claims, policies, customers, handlers, and docs."""
    claims_res = api_client.get("/api/claims")
    assert claims_res.status_code == 200
    claims = claims_res.json()
    assert len(claims) == 25
    assert claims[0]["claim_id"] == "CLM-1001"
    assert claims[0]["status"] == "waiting"

    claim_res = api_client.get("/api/claims/CLM-1001")
    assert claim_res.status_code == 200
    claim = claim_res.json()
    assert claim["claim_id"] == "CLM-1001"
    assert claim["amount_claimed"] == 420.0
    assert len(claim["items"]) == 3
    assert len(claim["documents"]) == 4
    assert claim["steps"] == []

    policy_res = api_client.get("/api/policies/POL-2001")
    assert policy_res.status_code == 200
    policy = policy_res.json()
    assert policy["plan"] == "premium"
    assert policy["plan_details"]["trip_delay_max"] == 800.0
    assert policy["add_on_details"] == []

    policy_addon_res = api_client.get("/api/policies/POL-2009")
    assert policy_addon_res.status_code == 200
    policy_addon = policy_addon_res.json()
    assert policy_addon["add_ons"] == ["electronics_plus"]
    assert policy_addon["add_on_details"][0]["electronics_per_item_limit"] == 1200.0

    customer_res = api_client.get("/api/customers/CUS-3001")
    assert customer_res.status_code == 200
    customer = customer_res.json()
    assert customer["name"] == "Maya Patel"
    assert len(customer["previous_claims"]) == 1

    handlers_res = api_client.get("/api/handlers")
    assert handlers_res.status_code == 200
    handlers = handlers_res.json()
    assert len(handlers) == 3
    assert handlers[0]["handler_id"] == "HND-01"

    wording_res = api_client.get("/api/policy-wording")
    assert wording_res.status_code == 200
    wording = wording_res.json()
    assert wording["version"] == "2026.1"
    assert "# UnderCover Travel Insurance: Policy Wording" in wording["content"]

    instructions_res = api_client.get("/api/instructions")
    assert instructions_res.status_code == 200
    assert "UnderCover Agent" in instructions_res.json()["instructions"]


def test_not_found_responses(api_client: TestClient) -> None:
    """Verify 404 responses for unknown claim, policy, customer, and handler IDs."""
    assert api_client.get("/api/claims/CLM-9999").status_code == 404
    assert api_client.get("/api/policies/POL-9999").status_code == 404
    assert api_client.get("/api/customers/CUS-9999").status_code == 404
    assert (
        api_client.post(
            "/api/claims/CLM-1001/sign-off", json={"handler_id": "HND-99"}
        ).status_code
        == 404
    )


def test_steps_and_approve_under_limit(api_client: TestClient) -> None:
    """Verify recording steps, approving a claim <= $1,000, and paying it."""
    step1 = api_client.post(
        "/api/claims/CLM-1001/steps",
        json={"message": "Reading claim CLM-1001"},
    )
    assert step1.status_code == 200
    data1 = step1.json()
    assert data1["status"] == "in_progress"
    assert len(data1["steps"]) == 1
    assert data1["steps"][0]["step_number"] == 1

    step2 = api_client.post(
        "/api/claims/CLM-1001/steps",
        json={"message": "Checking policy POL-2001"},
    )
    assert step2.status_code == 200
    assert len(step2.json()["steps"]) == 2

    dec_res = api_client.post(
        "/api/claims/CLM-1001/decision",
        json={
            "decision": "approve",
            "payout": 420.0,
            "policy_section": "Section 3: Trip Delay",
            "reason": "Flight home was delayed over 6 hours due to crew problem.",
        },
    )
    assert dec_res.status_code == 200
    dec_data = dec_res.json()
    assert dec_data["status"] == "decided"
    assert dec_data["decision"] == "approve"
    assert dec_data["payout"] == 420.0
    assert dec_data["payment_status"] == "unpaid"

    pay_res = api_client.post(
        "/api/claims/CLM-1001/pay",
        json={"amount": 420.0},
    )
    assert pay_res.status_code == 200
    pay_data = pay_res.json()
    assert pay_data["status"] == "decided"
    assert pay_data["payment_status"] == "paid"
    assert pay_data["amount_paid"] == 420.0


def test_over_limit_payment_blocked_until_handler_sign_off(
    api_client: TestClient,
) -> None:
    """Verify payouts over $1,000 wait for sign-off and block direct payment."""
    dec_res = api_client.post(
        "/api/claims/CLM-1003/decision",
        json={
            "decision": "approve",
            "payout": 3750.0,
            "policy_section": "Section 7: Emergency Medical",
            "reason": "Covered emergency wrist fracture treatment less $50 deductible.",
        },
    )
    assert dec_res.status_code == 200
    dec_data = dec_res.json()
    assert dec_data["status"] == "waiting_for_sign_off"
    assert dec_data["payment_status"] == "pending_sign_off"
    assert dec_data["payout"] == 3750.0

    blocked_pay = api_client.post(
        "/api/claims/CLM-1003/pay",
        json={"amount": 3750.0},
    )
    assert blocked_pay.status_code == 409

    still_waiting = api_client.get("/api/claims/CLM-1003").json()
    assert still_waiting["status"] == "waiting_for_sign_off"
    assert still_waiting["payment_status"] == "pending_sign_off"
    assert still_waiting["amount_paid"] == 0.0

    sign_off_res = api_client.post(
        "/api/claims/CLM-1003/sign-off",
        json={"handler_id": "HND-01"},
    )
    assert sign_off_res.status_code == 200
    signed_data = sign_off_res.json()
    assert signed_data["status"] == "decided"
    assert signed_data["payment_status"] == "paid"
    assert signed_data["amount_paid"] == 3750.0
    assert signed_data["signed_off_by"] == "HND-01"


def test_decline_and_invalid_payment_or_sign_off(api_client: TestClient) -> None:
    """Verify declined claims cannot be paid or signed off."""
    dec_res = api_client.post(
        "/api/claims/CLM-1004/decision",
        json={
            "decision": "decline",
            "payout": 0.0,
            "policy_section": "Section 4: Baggage Delay",
            "reason": "Not eligible.",
        },
    )
    assert dec_res.status_code == 200
    assert dec_res.json()["status"] == "decided"
    assert dec_res.json()["payment_status"] == "unpaid"

    pay_res = api_client.post("/api/claims/CLM-1004/pay", json={"amount": 100.0})
    assert pay_res.status_code == 409

    sign_res = api_client.post(
        "/api/claims/CLM-1004/sign-off", json={"handler_id": "HND-01"}
    )
    assert sign_res.status_code == 409
