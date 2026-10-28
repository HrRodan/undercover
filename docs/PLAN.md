# UnderCover Claims Pilot Implementation Plan

## Goal

Build the UnderCover Travel Insurance claims pilot: a FastAPI + SQLAlchemy 2.x ORM backend (backed by SQLite) seeded from `data/`, a LangChain claims agent (`create_agent` via OpenRouter) that reads claims and its instructions exclusively through the backend API, and a React 19 + TypeScript dashboard where handlers monitor the queue, inspect full claims, watch the agent work step by step, sign off payouts over $1,000, and view the agent's instructions read-only.

## Architecture Overview

- **Backend (`backend/`)**: FastAPI application backed by SQLite via SQLAlchemy 2.x ORM (`DeclarativeBase`, `Mapped`, `mapped_column`, `Session`, `select`). Initializes the schema (`Base.metadata.create_all`) and seeds the 25 queue claims (`claims.json`), 50 policies (`policies.json`), 49 customers (`customers.json`), 3 plans and 3 add-ons (`plans.json`), company settings (`company.json`), 3 handlers (`handlers.json`), policy wording (`policy_wording.md`), and default agent instructions from `data/` (never reading `data/evals/`, `data/claims_manual.md`, or `data/security/`). Exposes typed REST endpoints where every route has an explicit `operation_id`, a one-line docstring, `Annotated[Session, Depends(get_session)]` injection (`FAST002`), return-type annotations without redundant `response_model` (`FAST001`), and no optional inputs. Enforces the $1,000 payout approval limit in the backend so payments over $1,000 are blocked until a handler signs off, even if the agent calls the payment endpoint directly.
- **Agent (`agent/`)**: Single entry point `run(claim_id: str, thread_id: str, llm: BaseChatModel | None = None) -> str` built with LangChain's `create_agent` and `ChatOpenAI` pointed at OpenRouter (`openai/gpt-6-luna` with `reasoning_effort="low"` by default, or `MODEL_NAME`). Fetches its system prompt from `GET /api/instructions` and uses backend API tools (`get_claim`, `get_policy`, `get_customer`, `get_policy_wording`, `decide_claim`, `pay_claim`) while recording each step via `POST /api/claims/{claim_id}/steps`.
- **Dashboard (`dashboard/`)**: React 19 + Vite + TypeScript single-page workspace styled in vanilla CSS with custom properties following `docs/BRAND.md` (Nordic Obsidian & Precision Daylight). Provides the claims queue table, full claim inspection panel, live step-by-step agent progress feed, handler sign-off workflow for approvals over $1,000, and a read-only agent instructions view.
- **End-to-End Tests (`e2e/`)**: Playwright test suite verifying the full handler workflow against the running backend and dashboard.

---

## Phase 1: SQLAlchemy Database Models & Seed Data Layer

### What This Phase Builds

Creates the SQLAlchemy 2.x ORM persistence layer (`DeclarativeBase`, `Mapped`, `mapped_column`, `create_engine`, `sessionmaker`) and seed loader for UnderCover's operational records. It loads `company.json`, `plans.json`, `policies.json`, `customers.json`, `handlers.json`, `claims.json`, and `policy_wording.md` from `data/` into SQLAlchemy ORM models, initializes every claim in the `waiting` state, and stores the read-only agent instructions. It never reads `data/evals/`, `data/claims_manual.md`, or `data/security/`.

### Files Affected

- Modify: `pyproject.toml` (promote `sqlalchemy>=2.1.3` into main `project.dependencies` via `uv add sqlalchemy`)
- Create: `backend/models.py` (SQLAlchemy 2.x `DeclarativeBase` and typed ORM models for claims, claim steps, policies, customers, plans, add-ons, handlers, company settings, policy wording, and agent instructions)
- Create: `backend/db.py` (SQLAlchemy engine with `connect_args={"check_same_thread": False}`, session factory, FastAPI `Annotated[Session, Depends(get_session)]` dependency, `Base.metadata.create_all`, and idempotent seeding from `data/` using SQLAlchemy `Session` and `select`)
- Create: `backend/schemas.py` (Pydantic response and request models with no optional inputs on route payloads)
- Create: `backend/tests/test_db.py` (unit tests for SQLAlchemy schema initialization, ORM queries, seed counts, and data integrity)

### Why This Approach

Using SQLAlchemy 2.x ORM (`Mapped` / `mapped_column`) for all database schema definitions, queries, and mutations provides strict static typing (`pyright`), clean session lifecycle management per request, and seamless future migration to PostgreSQL/Supabase in Week 2 without raw SQL strings. A configurable database path (`UNDERCOVER_DB_PATH`, defaulting to a local SQLite database and isolated temporary/in-memory SQLite databases in `pytest`) gives fast, deterministic tests and a single source of truth for claim statuses (`waiting`, `in_progress`, `waiting_for_sign_off`, `decided`), decisions (`approve`, `decline`, `refer`), payouts, payment states (`unpaid`, `pending_sign_off`, `paid`), and step-by-step agent activity logs. Calling `init_db()` on startup ensures `TestClient(app)` works both with and without a `with` block.

### Success Criteria

- [x] All database tables, queries, and writes use SQLAlchemy 2.x ORM (`Session`, `select`, `DeclarativeBase`, `Mapped`, `mapped_column`) with zero direct `sqlite3` calls.
- [x] Unit tests in `backend/tests/test_db.py` verify that seeding loads 25 claims from `data/claims.json`, 50 policies from `data/policies.json`, 49 customers from `data/customers.json`, 3 plans and 3 add-ons from `data/plans.json`, 3 handlers from `data/handlers.json`, company settings (`payout_approval_limit == 1000.0`), and `data/policy_wording.md`.
- [x] Unit tests verify that every seeded claim starts with `status = "waiting"`, `payment_status = "unpaid"`, and an empty steps list, and that re-running `init_db()` is idempotent.
- [x] Unit tests verify that `data/evals/`, `data/claims_manual.md`, and `data/security/` are never read or stored in the database.
- [x] Command `uv run pytest backend/tests/test_db.py -q` passes with zero warnings or errors.
- [x] Command `npm run check:python` passes formatting, lint (`ruff`), type checking (`pyright`), and coverage (`>= 80%`).

---

## Phase 2: Backend Read, Decision, Payment & Sign-Off API

### What This Phase Builds

Exposes the FastAPI routes in `backend/main.py` for reading claims, policies, customers, handlers, policy wording, and agent instructions, and for recording agent steps, decisions, claim payments, and handler sign-offs:

- `GET /api/health` (`operation_id="health"`)
- `GET /api/claims` (`operation_id="list_claims"`)
- `GET /api/claims/{claim_id}` (`operation_id="get_claim"`)
- `GET /api/policies/{policy_id}` (`operation_id="get_policy"`)
- `GET /api/customers/{customer_id}` (`operation_id="get_customer"`)
- `GET /api/handlers` (`operation_id="list_handlers"`)
- `GET /api/policy-wording` (`operation_id="get_policy_wording"`)
- `GET /api/instructions` (`operation_id="get_instructions"`)
- `POST /api/claims/{claim_id}/steps` (`operation_id="record_claim_step"`)
- `POST /api/claims/{claim_id}/decision` (`operation_id="decide_claim"`)
- `POST /api/claims/{claim_id}/pay` (`operation_id="pay_claim"`)
- `POST /api/claims/{claim_id}/sign-off` (`operation_id="sign_off_claim"`)

### Files Affected

- Modify: `backend/main.py` (initialize DB and register all REST routes using `DbSession = Annotated[Session, Depends(get_session)]`)
- Modify: `backend/schemas.py` (request/response models for claims, policies, customers, handlers, decisions, payments, steps, and sign-offs)
- Modify: `backend/db.py` (SQLAlchemy `Session` query and mutation helpers for claims, steps, decisions, payments, and sign-offs)
- Create: `backend/tests/test_api.py` (API tests covering all endpoints, 404s, state transitions, idempotency, and the $1,000 payment guardrail)

### Why This Approach

Separating `decide_claim` (`POST /api/claims/{claim_id}/decision`) from `pay_claim` (`POST /api/claims/{claim_id}/pay`) satisfies `docs/TECH_STACK.md` and enforces the core business rule in `docs/SPEC.md`:
- Recording a step via `POST /api/claims/{claim_id}/steps` on a `waiting` claim transitions its `status` to `in_progress` and appends the step in order.
- When `decide_claim` is called with `decision="approve"` and `payout > 1000.0`, the claim status becomes `waiting_for_sign_off`, `payment_status` becomes `pending_sign_off`, and `signed_off_by` is cleared.
- If the agent or any caller invokes `POST /api/claims/{claim_id}/pay` while `status == "waiting_for_sign_off"` (or when `amount > 1000.0` without handler sign-off, or when the claim is not approved), the backend blocks the payment with HTTP `409 Conflict` and keeps `payment_status = "pending_sign_off"`.
- For approved claims with `0 < payout <= 1000.0`, `decide_claim` marks `status = "decided"` and `pay_claim` records the payment (`payment_status = "paid"`, `amount_paid = amount`). For `decline` or `refer`, `status = "decided"` and `payment_status = "unpaid"`.
- When a handler calls `POST /api/claims/{claim_id}/sign-off` with `{ "handler_id": "HND-01" }` on a claim waiting for sign-off, the backend validates the handler, records `signed_off_by = "HND-01"`, releases the payment (`payment_status = "paid"`, `amount_paid = payout`), and marks the claim `decided`.

### Success Criteria

- [x] Every FastAPI route defines an explicit `operation_id`, a one-line docstring, `Annotated` dependency injection (`FAST002`), and no optional inputs.
- [x] `GET /api/claims` returns 25 claims in queue order with status `waiting`.
- [x] `GET /api/claims/CLM-1001` returns the full claim including `story`, `items`, `documents`, `amount_claimed`, `status`, and `steps`.
- [x] `GET /api/policies/POL-2001` returns the policy along with its resolved `plan_details` (`premium`) and `add_on_details`.
- [x] `GET /api/customers/CUS-3001` returns the customer details and `previous_claims`.
- [x] `GET /api/handlers` returns the 3 handlers from `data/handlers.json`.
- [x] `GET /api/policy-wording` returns `{ "version": "2026.1", "content": "# UnderCover Travel Insurance: Policy Wording..." }`.
- [x] `GET /api/instructions` returns `{ "instructions": "..." }` containing the read-only system prompt for the agent.
- [x] `POST /api/claims/CLM-1001/decision` with `{ "decision": "approve", "payout": 420.0, "policy_section": "Section 3: Trip Delay", "reason": "..." }` followed by `POST /api/claims/CLM-1001/pay` with `{ "amount": 420.0 }` transitions the claim to `status = "decided"` and `payment_status = "paid"`.
- [x] `POST /api/claims/CLM-1003/decision` with `{ "decision": "approve", "payout": 3750.0, "policy_section": "Section 7: Emergency Medical", "reason": "..." }` sets `status = "waiting_for_sign_off"` and `payment_status = "pending_sign_off"`. Calling `POST /api/claims/CLM-1003/pay` with `{ "amount": 3750.0 }` before sign-off returns HTTP `409` and does not mark the claim paid.
- [x] `POST /api/claims/CLM-1003/sign-off` with `{ "handler_id": "HND-01" }` transitions `CLM-1003` to `status = "decided"`, `payment_status = "paid"`, and records `signed_off_by = "HND-01"`.
- [x] Command `npm run check:python` passes with `>= 80%` test coverage.

---

## Phase 3: The UnderCover Agent & Backend Run Trigger

### What This Phase Builds

Implements the UnderCover Agent in `agent/main.py` using LangChain's `create_agent` and connects it to a backend run endpoint (`POST /api/claims/{claim_id}/run`) so claims can be processed either directly via `agent.main.run(claim_id, thread_id)` or triggered from the dashboard.

### Files Affected

- Modify: `agent/main.py` (implement backend API tools, step logging, instruction retrieval from `GET /api/instructions`, and `run(claim_id, thread_id, llm=None)`)
- Modify: `agent/tests/test_agent.py` (unit tests with `StubModel` covering tool execution, step logging, approve under $1,000, approve over $1,000 where payment is blocked pending sign-off, decline, and refer)
- Modify: `backend/main.py` (add `POST /api/claims/{claim_id}/run` with `operation_id="run_claim_agent"` to reset steps, mark the claim `in_progress`, and run the agent)
- Modify: `backend/tests/test_api.py` (test `POST /api/claims/{claim_id}/run` with a stubbed agent runner)

### Why This Approach

- The agent accesses all data strictly through the backend's HTTP API (`GET /api/instructions`, `GET /api/claims/{claim_id}`, `GET /api/policies/{policy_id}`, `GET /api/customers/{customer_id}`, `GET /api/policy-wording`, `POST /api/claims/{claim_id}/decision`, `POST /api/claims/{claim_id}/pay`).
- Each tool call has at most 5 parameters (`PLR0913`) and records a human-readable step via `POST /api/claims/{claim_id}/steps` (for example, `"Reading claim CLM-1001"`, `"Checking policy POL-2001 and plan limits"`, `"Reviewing customer claim history for CUS-3001"`, `"Reading policy wording"`, `"Recording decision: approve ($420.00)"`, `"Requesting payout of $420.00"`), enabling the dashboard to show what the agent is doing step by step.
- When `pay_claim` receives HTTP `409` because the payout exceeds $1,000, the tool returns a clear status message (`"Payment of $3,750.00 is blocked pending handler sign-off."`) and logs that step so the agent finishes cleanly while the claim waits in `waiting_for_sign_off`.
- The agent instructions served by `GET /api/instructions` guide the model to check covered trip dates, policy purchase date (known events / 60-day pre-existing look-back), waiting periods, per-item limits (`$150` Economy / `$300` Premium / `$500` First, or `$1,200` with Electronics Plus), carrier/supplier deductions first, deductibles (`$100` Economy / `$50` Premium / `$0` First on Baggage and Emergency Medical only), benefit maximums, required documents (referring when a required document is missing or judgment is needed), and concise 2-3 sentence explanations citing the policy section.

### Success Criteria

- [x] `agent.main.run(claim_id, thread_id, llm=...)` fetches instructions from `GET /api/instructions`, invokes `create_agent`, runs the tool loop against the backend API, and returns the final message text.
- [x] Unit tests in `agent/tests/test_agent.py` verify each tool (`get_claim`, `get_policy`, `get_customer`, `get_policy_wording`, `decide_claim`, `pay_claim`) and verify that steps are recorded on the claim in order.
- [x] Unit tests verify that when the agent approves a claim over $1,000 and calls `pay_claim`, the tool gracefully handles the backend's 409 block and leaves the claim in `waiting_for_sign_off`.
- [x] `POST /api/claims/CLM-1001/run` transitions the claim through `in_progress`, runs the agent, and returns the updated claim detail.
- [x] Command `npm run check:python` passes all `ruff`, `pyright`, and `pytest` checks with `>= 80%` coverage and zero live LLM calls in tests.

---

## Phase 4: Dashboard Foundation, Brand Theme & Claims Queue

### What This Phase Builds

Sets up the **Nordic Obsidian & Precision Daylight** design system in `dashboard/` following `docs/BRAND.md` and builds the main operational layout and Claims Queue screen.

### Files Affected

- Modify: `dashboard/index.html` (load Google Fonts: `Space Grotesk`, `Plus Jakarta Sans`, `Fraunces`, and `Geist Mono`)
- Create: `dashboard/src/styles.css` (CSS custom properties for light and dark surfaces, typography, semantic status pills, tabular numeric columns, focus rings, and responsive two-column workspace layout)
- Create: `dashboard/src/types.ts` (strict TypeScript interfaces matching the backend schemas)
- Create: `dashboard/src/api.ts` (typed `fetch` client for all backend endpoints)
- Create: `dashboard/src/components/StatusBadge.tsx` (semantic status and decision badges pairing a 12%-opacity tint, 1px border, and label text)
- Create: `dashboard/src/components/ClaimsQueue.tsx` (scannable queue table with status filter tabs: All, Waiting, In progress, Waiting for sign-off, Decided; summary metrics; accessible selection controls; right-aligned USD currency columns in `Geist Mono`)
- Modify: `dashboard/src/main.tsx` (import `styles.css`)

### Why This Approach

Building the typed API client, brand tokens, and queue table as modular components keeps each file well within the ESLint structural limits (max 200 lines per function, max 500 lines per file, cyclomatic complexity <= 15, max 5 parameters) while delivering the exact color palette (`#6366F1` Electric Indigo, `#10B981` Jade Emerald, `#F59E0B` Amber Gold, `#0EA5E9` Sky Cyan, `#F43F5E` Crimson Rose) and typography specified in `docs/BRAND.md`.

### Success Criteria

- [x] Component tests verify `ClaimsQueue` renders claims with formatted USD amounts (`$420.00`), claim IDs and policy IDs in monospace, and semantic badges for `Waiting`, `In progress`, `Waiting for sign-off`, and `Decided`.
- [x] Component tests verify filtering the queue by status (`waiting`, `in_progress`, `waiting_for_sign_off`, `decided`).
- [x] No emojis appear anywhere in the UI or source files, and all interactive elements pass `eslint-plugin-jsx-a11y-x` checks.
- [x] Command `npm run check:ts` passes `prettier`, `eslint`, `tsc`, and `vitest` with `>= 80%` coverage.

---

## Phase 5: Claim Detail View, Live Agent Steps, Sign-Off & Instructions Screen

### What This Phase Builds

Completes the dashboard by adding the full Claim Detail view, the live Step-by-Step Agent Activity panel, the Handler Sign-Off action for approvals over $1,000, the "Run Agent" trigger, and the read-only Agent Instructions screen.

### Files Affected

- Create: `dashboard/src/components/ClaimDetail.tsx` (displays customer story, claimed items table, supporting documents, policy & plan coverage details, customer claim history, agent decision card with payout/section/explanation, "Run Agent" button, and Handler Sign-Off bar for claims in `waiting_for_sign_off`)
- Create: `dashboard/src/components/AgentSteps.tsx` (renders the step-by-step trace of what the agent is doing or did on the claim, updating live while the claim is `in_progress`)
- Create: `dashboard/src/components/InstructionsView.tsx` (read-only view of the agent's instructions fetched from `GET /api/instructions` and the policy wording reference)
- Modify: `dashboard/src/App.tsx` (wire header navigation between Claims Queue + Claim Detail workspace and the read-only Agent Instructions view, plus live polling when a claim is `in_progress`)
- Modify: `dashboard/src/App.test.tsx` (comprehensive Vitest tests covering queue loading, selecting a claim to see full details/documents/policy/customer history, running the agent and seeing step-by-step progress, signing off a >$1,000 claim, and switching to the read-only instructions view)

### Why This Approach

Handlers can select any claim in the queue to inspect the full record side by side with the agent's live steps and decision. When a handler triggers the agent on a claim, the UI marks the claim `In progress` and polls `GET /api/claims/{claim_id}` so the step list updates smoothly (`150ms cubic-bezier(0.16, 1, 0.3, 1)`) without layout shift. When an approved payout exceeds $1,000, the Handler Sign-Off panel lets the handler select their handler profile (`Dana Whitfield`, `Marcus Oyelaran`, or `Priya Raman` loaded from `GET /api/handlers`) and sign off to release the payment.

### Success Criteria

- [x] Component tests in `dashboard/src/App.test.tsx` verify:
  - Selecting a claim loads and displays the customer's story, itemized claim breakdown, attached documents, policy plan limits, and previous claims.
  - Clicking "Run Agent" calls `POST /api/claims/{claim_id}/run` and displays the step-by-step trace and resulting decision, payout, policy section, and 2-3 sentence reason.
  - Viewing a claim in `waiting_for_sign_off` shows that payment is held pending handler sign-off and allows a handler to click "Sign Off & Release Payment", calling `POST /api/claims/{claim_id}/sign-off`.
  - Switching to the "Agent Instructions" tab displays the agent's instructions in a read-only view (`GET /api/instructions`).
- [x] Command `npm run check:ts` passes `prettier --check`, `eslint`, `tsc`, and `vitest --coverage` with `>= 80%` coverage.

---

## Phase 6: End-to-End Playwright Suite & Full Verification

### What This Phase Builds

Replaces the hello-world smoke test with a comprehensive Playwright E2E suite in `e2e/health.spec.ts`, verifies every screen and workflow in a headless Chromium browser via `playwright-cli`, and updates `docs/STATUS.md`.

### Files Affected

- Modify: `e2e/health.spec.ts` (validate the full UnderCover pilot end-to-end across repeatable runs)
- Modify: `docs/STATUS.md` (document all backend routes, agent tools, dashboard views, and how to run and test the pilot)

### Why This Approach

Testing the integrated frontend and backend in Playwright proves that the SQLAlchemy-seeded database, FastAPI routes, status transitions, >$1,000 payment block and handler sign-off, step-by-step agent trace, and read-only instructions screen work together cleanly and repeatably.

### Success Criteria

- [x] Playwright E2E tests (`npm run e2e`) verify:
  - The dashboard loads the 25-claim queue with statuses (`Waiting`, `In progress`, `Waiting for sign-off`, `Decided`) and USD amounts.
  - Selecting a claim (`CLM-1001`) shows the customer story, claimed items, supporting documents, policy details, and customer history.
  - Recording steps and a decision (`<= $1,000`) updates the claim step-by-step and marks it `Decided` with the explanation and policy section visible.
  - Recording an approved decision over `$1,000` (`CLM-1003`, `$3,750.00`) blocks payment (`POST /api/claims/CLM-1003/pay` returns `409`), shows `Waiting for sign-off` in the UI, and allows a handler to sign off in the UI to release the payment and mark the claim `Decided`.
  - Opening the "Agent Instructions" view displays the agent's instructions read-only.
- [x] Interactive verification with `playwright-cli` confirms visual hierarchy, light/dark surface contrast, tabular numerals, and zero console or page errors on the live app (`http://localhost:5173`).
- [x] `docs/STATUS.md` accurately documents the built pilot.
- [x] Command `npm run check` (`npm run check:python && npm run check:ts && npm run e2e`) passes completely.
