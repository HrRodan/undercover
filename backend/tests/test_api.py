"""API tests for the UnderCover backend."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import main as backend_main
from backend.main import app


@pytest.fixture
def api_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Return a TestClient configured against an isolated SQLite database."""
    monkeypatch.setenv("UNDERCOVER_DB_PATH", str(tmp_path / "api_test.db"))
    return TestClient(app)


def test_read_endpoints_and_config(api_client: TestClient) -> None:
    """Verify read endpoints for config, claims, policies, customers, and docs."""
    cfg_res = api_client.get("/api/config")
    assert cfg_res.status_code == 200
    cfg = cfg_res.json()
    assert cfg["policy_wording_file"] == "policy_wording_short_optimized.md"
    assert cfg["claims_manual_file"] == "claims_manual.md"

    claims_res = api_client.get("/api/claims")
    assert claims_res.status_code == 200
    claims = claims_res.json()
    assert len(claims) == 25
    assert claims[0]["claim_id"] == "CLM-1001"
    assert claims[0]["status"] == "waiting"
    assert claims[0]["attempts"] == 0
    assert claims[0]["sections_read"] == []

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


def test_wording_manual_and_instructions_endpoints(api_client: TestClient) -> None:
    """Verify policy wording, claims manual, and dual instructions endpoints."""
    wording_res = api_client.get("/api/policy-wording")
    assert wording_res.status_code == 200
    wording = wording_res.json()
    assert wording["version"] == "2026.1"
    assert "# UnderCover Travel Insurance: Policy Wording" in wording["content"]

    manual_res = api_client.get("/api/claims-manual")
    assert manual_res.status_code == 200
    manual = manual_res.json()
    assert manual["version"] == "2026.2"
    assert "# UnderCover Claims Handling Manual" in manual["content"]

    instructions_res = api_client.get("/api/instructions")
    assert instructions_res.status_code == 200
    inst_data = instructions_res.json()
    assert "UnderCover Queue Agent" in inst_data["queue_instructions"]
    assert "UnderCover Claim Subagent" in inst_data["claim_instructions"]


def test_document_sections_and_search(api_client: TestClient) -> None:
    """Verify listing, reading, searching, and recording read document sections."""
    wording_secs = api_client.get("/api/documents/policy_wording/sections")
    assert wording_secs.status_code == 200
    w_titles = [s["title"] for s in wording_secs.json()]
    assert "Limits" in w_titles
    assert "Baggage" in w_titles

    manual_secs = api_client.get("/api/documents/claims_manual/sections")
    assert manual_secs.status_code == 200
    m_titles = [s["title"] for s in manual_secs.json()]
    assert "7. Interpretation notes" in m_titles
    assert "9. Repeat claims" in m_titles

    sec_detail = api_client.get("/api/documents/claims_manual/sections/7")
    assert sec_detail.status_code == 200
    assert "Wild animals" in sec_detail.json()["content"]

    rec_res = api_client.post(
        "/api/claims/CLM-1020/sections-read",
        json={"doc_name": "claims_manual", "section_id": "7"},
    )
    assert rec_res.status_code == 200
    claim_20 = api_client.get("/api/claims/CLM-1020").json()
    assert "Claims Manual — 7. Interpretation notes" in claim_20["sections_read"]
    assert any(
        "Reading Claims Manual — 7. Interpretation notes" in s["message"]
        for s in claim_20["steps"]
    )

    search_res = api_client.post(
        "/api/documents/search",
        json={"query": "wild animals monkey"},
    )
    assert search_res.status_code == 200
    results = search_res.json()
    assert len(results) >= 1
    assert any("Wild animals" in r["content"] for r in results)

    assert api_client.get("/api/documents/unknown/sections").status_code == 404
    assert (
        api_client.get("/api/documents/claims_manual/sections/999").status_code == 404
    )


def test_todos_and_failure_lifecycle(api_client: TestClient) -> None:
    """Verify storing to-do items and the 1st/2nd claim failure state transitions."""
    todos_payload = {
        "todos": [
            {
                "claim_id": "CLM-1001",
                "description": "Decide claim CLM-1001",
                "status": "to_do",
                "result_summary": "",
            },
            {
                "claim_id": "CLM-1002",
                "description": "Decide claim CLM-1002",
                "status": "in_progress",
                "result_summary": "",
            },
        ]
    }
    put_res = api_client.put("/api/todos", json=todos_payload)
    assert put_res.status_code == 200
    assert len(put_res.json()) == 2

    get_res = api_client.get("/api/todos")
    assert get_res.status_code == 200
    assert get_res.json()[0]["claim_id"] == "CLM-1001"
    assert get_res.json()[1]["status"] == "in_progress"

    # First failure on CLM-1002 resets status to waiting (attempts == 1)
    fail1 = api_client.post(
        "/api/claims/CLM-1002/fail",
        json={"error": "Model provider timeout"},
    )
    assert fail1.status_code == 200
    f1_data = fail1.json()
    assert f1_data["status"] == "waiting"
    assert f1_data["attempts"] == 1
    assert api_client.get("/api/todos").json()[1]["status"] == "to_do"

    # Second failure on CLM-1002 marks status left_for_handler (attempts == 2)
    fail2 = api_client.post(
        "/api/claims/CLM-1002/fail",
        json={"error": "Model provider timeout again"},
    )
    assert fail2.status_code == 200
    f2_data = fail2.json()
    assert f2_data["status"] == "left_for_handler"
    assert f2_data["attempts"] == 2
    assert api_client.get("/api/todos").json()[1]["status"] == "left_for_handler"


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


def test_steps_approve_and_block_double_decision_or_payment(
    api_client: TestClient,
) -> None:
    """Verify recording steps, approving and paying <= $1,000, and blocking repeats."""
    step1 = api_client.post(
        "/api/claims/CLM-1001/steps",
        json={"message": "Reading claim CLM-1001"},
    )
    assert step1.status_code == 200
    assert step1.json()["status"] == "in_progress"

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
    assert dec_res.json()["status"] == "decided"

    # Duplicate decision must be rejected with 409
    dup_dec = api_client.post(
        "/api/claims/CLM-1001/decision",
        json={
            "decision": "decline",
            "payout": 0.0,
            "policy_section": "Section 3: Trip Delay",
            "reason": "Changed mind.",
        },
    )
    assert dup_dec.status_code == 409

    pay_res = api_client.post(
        "/api/claims/CLM-1001/pay",
        json={"amount": 420.0},
    )
    assert pay_res.status_code == 200
    assert pay_res.json()["payment_status"] == "paid"

    # Duplicate payment must be rejected with 409
    dup_pay = api_client.post(
        "/api/claims/CLM-1001/pay",
        json={"amount": 420.0},
    )
    assert dup_pay.status_code == 409


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


def test_run_claim_and_queue_endpoints(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify POST /api/claims/{claim_id}/run and POST /api/queue/run."""

    def stub_invoke(claim_id: str) -> None:
        api_client.post(
            f"/api/claims/{claim_id}/steps",
            json={"message": f"Reading claim {claim_id}"},
        )
        api_client.post(
            f"/api/claims/{claim_id}/decision",
            json={
                "decision": "approve",
                "payout": 420.0,
                "policy_section": "Section 3: Trip Delay",
                "reason": "Covered delay.",
            },
        )
        api_client.post(
            f"/api/claims/{claim_id}/pay",
            json={"amount": 420.0},
        )

    monkeypatch.setattr(backend_main, "invoke_claim_agent", stub_invoke)
    res = api_client.post("/api/claims/CLM-1001/run")
    assert res.status_code == 200
    assert res.json()["status"] == "decided"

    def stub_queue(cap: int) -> str:
        return f"Processed up to {cap} claims."

    monkeypatch.setattr(backend_main, "invoke_queue_agent", stub_queue)
    q_res = api_client.post("/api/queue/run", json={"cap": 5})
    assert q_res.status_code == 200
    q_data = q_res.json()
    assert q_data["status"] == "completed"
    assert q_data["cap"] == 5
    assert q_data["summary"] == "Processed up to 5 claims."

    reset_res = api_client.post("/api/claims/reset")
    assert reset_res.status_code == 200
    assert reset_res.json()[0]["status"] == "waiting"
