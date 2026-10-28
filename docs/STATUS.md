# Status

## Built so far

- **Phase 1 — SQLAlchemy Database Models & Seed Data Layer**:
  - `backend/models.py`: SQLAlchemy 2.x ORM models (`CompanyRecord`, `PlanRecord`, `AddOnRecord`, `PolicyRecord`, `CustomerRecord`, `HandlerRecord`, `ClaimRecord`, `ClaimStepRecord`, `PolicyWordingRecord`, `InstructionsRecord`).
  - `backend/db.py`: SQLAlchemy engine, `get_session` dependency, and idempotent seed loader for `company.json`, `plans.json`, `policies.json`, `customers.json`, `handlers.json`, `claims.json` (initialized in `waiting` state), `policy_wording.md`, and read-only agent instructions.
  - `backend/schemas.py`: Typed Pydantic request and response models.
  - `backend/tests/test_db.py`: Unit tests verifying seed counts, initial claim states, idempotency, and protection of held-out/manual/security files.
- `backend/main.py`: `GET /api/health`
- `agent/`: entry point `run(claim_id, thread_id)`
- `dashboard/`: status page
- `e2e/`: Playwright smoke test
