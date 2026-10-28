# Status

## What's built

The UnderCover Travel Insurance claims pilot is complete:

- **Backend (`backend/`)**:
  - FastAPI application backed by SQLite via SQLAlchemy 2.x ORM (`backend/models.py`, `backend/db.py`, `backend/schemas.py`, `backend/main.py`).
  - Automatically creates tables and idempotently seeds the 25 queue claims (`claims.json`), 50 policies (`policies.json`), 49 customers (`customers.json`), 3 plans and 3 add-ons (`plans.json`), 3 handlers (`handlers.json`), company settings (`company.json`), policy wording (`policy_wording.md`), and read-only agent instructions.
  - Never reads `data/evals/`, `data/claims_manual.md`, or `data/security/`.
  - Routes (each with an explicit `operation_id`, one-line docstring, and no optional inputs):
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
    - `POST /api/claims/{claim_id}/pay` (`pay_claim`) — blocks payouts over $1,000 (`409 Conflict`) until a handler signs off
    - `POST /api/claims/{claim_id}/sign-off` (`sign_off_claim`)
    - `POST /api/claims/{claim_id}/run` (`run_claim_agent`)
- **Agent (`agent/main.py`)**:
  - Entry point `run(claim_id: str, thread_id: str, llm: BaseChatModel | None = None) -> str` built with LangChain's `create_agent` on OpenRouter (`openai/gpt-6-luna` with `reasoning_effort="low"` by default, or `MODEL_NAME`).
  - Reaches claims and its instructions exclusively through the backend REST API using tools (`check_backend`, `get_claim`, `get_policy`, `get_customer`, `get_policy_wording`, `decide_claim`, `pay_claim`) and logs each step on the claim.
- **Dashboard (`dashboard/`)**:
  - React 19, Vite, TypeScript, and vanilla CSS following `docs/BRAND.md` (Nordic Obsidian & Precision Daylight, light and dark mode).
  - Displays the filterable 25-claim queue (`ClaimsQueue`) with a **Run All Waiting** button, full claim inspection (`ClaimDetail`) with **Run Agent** / **Rerun Agent** controls, live step-by-step agent activity (`AgentSteps`), handler sign-off workflow for approvals over $1,000, and the read-only `Agent Instructions` & `Policy Wording` reference view (`InstructionsView`).
- **End-to-End Tests (`e2e/health.spec.ts`)**:
  - Playwright test suite verifying the 25-claim queue, full claim inspection, step-by-step trace, decision and payment under $1,000, >$1,000 payment block (`409`) and handler sign-off workflow, and the read-only Agent Instructions screen.

## How to run it

- Install dependencies: `uv sync` and `npm install`
- Start backend and dashboard in development: `npm run dev` (backend on `http://127.0.0.1:8000`, dashboard on `http://localhost:5173`)
- Run all verification checks: `npm run check` (`npm run check:python && npm run check:ts && npm run e2e`)
