# Status

## What's built

The UnderCover Travel Insurance claims pilot and the **Week 1 Day 5 Agent Harness (`docs/HARNESS.md`)** are complete:

- **Backend (`backend/`)**:
  - FastAPI application backed by SQLite via SQLAlchemy 2.x ORM (`backend/config.py`, `backend/models.py`, `backend/schemas.py`, `backend/seed.py`, `backend/documents.py`, `backend/queries.py`, `backend/db.py`, `backend/main.py`).
  - Centralised data file configuration in `backend/config.py` (`get_backend_config()`), defaulting to `policy_wording_short_optimized.md` (`POLICY_WORDING_FILE`) and `claims_manual.md` (`CLAIMS_MANUAL_FILE`).
  - Automatically creates tables and idempotently seeds the 25 queue claims (`claims.json`), 50 policies (`policies.json`), 49 customers (`customers.json`), 3 plans and 3 add-ons (`plans.json`), 3 handlers (`handlers.json`), company settings (`company.json`), policy wording (`policy_wording_short_optimized.md`), claims manual (`claims_manual.md`), and read-only instructions for both the master queue agent and the claim subagent.
  - Never reads `data/evals/` or `data/security/`.
  - Routes (each with an explicit `operation_id`, one-line docstring, and no optional inputs):
    - `GET /api/health` (`health`)
    - `GET /api/config` (`get_config`)
    - `GET /api/claims` (`list_claims`)
    - `GET /api/claims/{claim_id}` (`get_claim`)
    - `GET /api/policies/{policy_id}` (`get_policy`)
    - `GET /api/customers/{customer_id}` (`get_customer`)
    - `GET /api/handlers` (`list_handlers`)
    - `GET /api/policy-wording` (`get_policy_wording`)
    - `GET /api/claims-manual` (`get_claims_manual`)
    - `GET /api/documents/{doc_name}/sections` (`list_document_sections`)
    - `GET /api/documents/{doc_name}/sections/{section_id}` (`get_document_section`)
    - `POST /api/documents/search` (`search_document_sections`)
    - `POST /api/claims/{claim_id}/sections-read` (`record_claim_section_read`)
    - `GET /api/instructions` (`get_instructions`)
    - `GET /api/todos` (`get_todos`)
    - `PUT /api/todos` (`save_todos`)
    - `PUT /api/todos/{claim_id}` (`update_single_todo`)
    - `GET /api/queue-run` (`get_queue_run`)
    - `PUT /api/queue-run` (`update_queue_run`)
    - `POST /api/claims/{claim_id}/steps` (`record_claim_step`)
    - `POST /api/claims/{claim_id}/decision` (`decide_claim`) — blocks duplicate decisions (`409 Conflict`)
    - `POST /api/claims/{claim_id}/pay` (`pay_claim`) — blocks duplicate payments (`409 Conflict`) and payouts over $1,000 (`409 Conflict`) until a handler signs off
    - `POST /api/claims/{claim_id}/fail` (`fail_claim`) — puts 1st failure back to `waiting` (`attempts=1`) and marks 2nd failure `left_for_handler` (`attempts=2`)
    - `POST /api/claims/{claim_id}/sign-off` (`sign_off_claim`)
    - `POST /api/claims/{claim_id}/run` (`run_claim_agent`)
    - `POST /api/queue/run` (`run_claims_queue`)
    - `POST /api/claims/reset` (`reset_claims`)
- **Agent Harness (`agent/config.py`, `agent/tools.py`, `agent/main.py`, `agent/__main__.py`)**:
  - Centralised configuration in `agent/config.py` (`get_agent_config()`): `openai/gpt-6-luna` default (`MODEL_NAME`, `QUEUE_MODEL_NAME`, `CLAIM_MODEL_NAME`), `QUEUE_REASONING_EFFORT="medium"`, `CLAIM_REASONING_EFFORT="low"`, `MODEL_TIMEOUT_SECONDS=120`, `MODEL_MAX_RETRIES=3`.
  - Master queue agent (`run_queue(thread_id=..., cap=None, llm=None)`) plans the queue with `get_waiting_claims` and `write_todos`, delegates each claim via `work_claim` to a fresh claim subagent (`run(claim_id, thread_id, llm=None)`), enforces `cap` on subagent calls, and verifies completion with `check_missed_claims` plus automatic harness reconciliation.
  - Claim subagent looks up sections of `policy_wording` (`policy_wording_short_optimized.md`) and `claims_manual` (`claims_manual.md`) using `list_document_sections`, `search_documents`, and `read_document_section`, recording every read section and step on the claim.
  - Middleware (`@wrap_model_call` `model_retry_middleware` and `@wrap_tool_call` `tool_error_boundary_middleware`) and subagent recovery ensure transient errors never stop the queue run or leave a claim stuck in `in_progress`.
- **Dashboard (`dashboard/`)**:
  - React 19, Vite, TypeScript, and vanilla CSS following `docs/BRAND.md` (Nordic Obsidian & Precision Daylight, light and dark mode).
  - Displays the filterable 25-claim queue (`ClaimsQueue`, including `Left for handler`), a run cap selector (`5`, `10`, `All waiting (25)`), the live `Agent To-Do List` & handover summary (`TodoListPanel`), full claim inspection (`ClaimDetail`) including `Policy Wording & Manual Sections Read`, live step-by-step agent activity (`AgentSteps`), handler sign-off workflow for approvals over $1,000, and the read-only `Queue Agent Instructions`, `Claim Subagent Instructions`, `Policy Wording`, and `Claims Handling Manual` reference view (`InstructionsView`).
- **End-to-End Tests (`e2e/health.spec.ts`)**:
  - Playwright test suite verifying the 25-claim queue, Agent To-Do List, cap selector, reference sections read, automatic recovery (`Left for handler`), over-limit payment block (`409`) and handler sign-off workflow, and the read-only Queue & Claim Subagent Instructions and Claims Handling Manual screens.

## How to run it

- Install dependencies: `uv sync` and `npm install`
- Start backend and dashboard in development: `npm run dev` (backend on `http://127.0.0.1:8000`, dashboard on `http://localhost:5173`)
- Run the queue agent from the CLI with a cap: `uv run -m agent --cap 5` (or on a single claim: `uv run -m agent --claim CLM-1001`)
- Reset the database to restart all claims in `waiting` state: `npm run db:reset` (or click **Reset Queue** in the dashboard)
- Run all verification checks: `npm run check` (`npm run check:python && npm run check:ts && npm run e2e`)
