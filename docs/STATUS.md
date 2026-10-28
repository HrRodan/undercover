# Status

## Built so far

- **Phase 1 — SQLAlchemy Database Models & Seed Data Layer**:
  - `backend/models.py`: SQLAlchemy 2.x ORM models (`CompanyRecord`, `PlanRecord`, `AddOnRecord`, `PolicyRecord`, `CustomerRecord`, `HandlerRecord`, `ClaimRecord`, `ClaimStepRecord`, `PolicyWordingRecord`, `InstructionsRecord`).
  - `backend/db.py`: SQLAlchemy engine, `get_session` dependency, and idempotent seed loader for `company.json`, `plans.json`, `policies.json`, `customers.json`, `handlers.json`, `claims.json`, `policy_wording.md`, and read-only agent instructions.
  - `backend/schemas.py`: Typed Pydantic request and response models.
- **Phase 2 — Backend Read, Decision, Payment & Sign-Off API**:
  - `backend/main.py`: FastAPI routes with explicit `operation_id`s:
    - `GET /api/health` (`health`)
    - `GET /api/claims` (`list_claims`)
    - `GET /api/claims/{claim_id}` (`get_claim`)
    - `GET /api/policies/{policy_id}` (`get_policy`)
    - `GET /api/customers/{customer_id}` (`get_customer`)
    - `GET /api/handlers` (`list_handlers`)
    - `GET /api/policy-wording` (`get_policy_wording`)
    - `GET /api/instructions` (`get_instructions`)
    - `POST /api/claims/{claim_id}/steps` (`record_claim_step`)
    - `POST /api/claims/{claim_id}/decision` (`decide_claim`)
    - `POST /api/claims/{claim_id}/pay` (`pay_claim`) — blocks payouts over $1,000 until handler sign-off
    - `POST /api/claims/{claim_id}/sign-off` (`sign_off_claim`)
  - `backend/tests/test_api.py`: API tests covering all endpoints, 404s, step recording, decisions, payments, and the $1,000 sign-off guardrail.
- `agent/`: entry point `run(claim_id, thread_id)`
- `dashboard/`: status page
- `e2e/`: Playwright smoke test
