# Status

## Built so far

- **Phase 1 — SQLAlchemy Database Models & Seed Data Layer**:
  - `backend/models.py`, `backend/db.py`, `backend/schemas.py`, `backend/tests/test_db.py`
- **Phase 2 — Backend Read, Decision, Payment & Sign-Off API**:
  - `backend/main.py`, `backend/tests/test_api.py`
- **Phase 3 — The UnderCover Agent & Backend Run Trigger**:
  - `agent/main.py`, `agent/tests/test_agent.py`, `POST /api/claims/{claim_id}/run`
- **Phase 4 — Dashboard Foundation, Brand Theme & Claims Queue**:
  - `dashboard/index.html`, `dashboard/src/styles.css`, `dashboard/src/types.ts`, `dashboard/src/api.ts`, `dashboard/src/components/StatusBadge.tsx`, `dashboard/src/components/ClaimsQueue.tsx`
- **Phase 5 — Claim Detail View, Live Agent Steps, Sign-Off & Instructions Screen**:
  - `dashboard/src/components/ClaimDetail.tsx`: Full claim inspection (story, items, supporting documents, policy & plan coverage, customer history, decision card, "Run Agent" button, and Handler Sign-Off workflow for approvals over $1,000).
  - `dashboard/src/components/AgentSteps.tsx`: Step-by-step agent progress feed.
  - `dashboard/src/components/InstructionsView.tsx`: Read-only agent instructions and policy wording reference.
  - `dashboard/src/App.tsx` & `dashboard/src/App.test.tsx`: Two-column operational workspace, live step polling, theme toggle, and component test suite.
- `e2e/`: Playwright smoke test
