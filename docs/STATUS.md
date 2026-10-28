# Status

## Built so far

- **Phase 1 — SQLAlchemy Database Models & Seed Data Layer**:
  - `backend/models.py`: SQLAlchemy 2.x ORM models (`CompanyRecord`, `PlanRecord`, `AddOnRecord`, `PolicyRecord`, `CustomerRecord`, `HandlerRecord`, `ClaimRecord`, `ClaimStepRecord`, `PolicyWordingRecord`, `InstructionsRecord`).
  - `backend/db.py`: SQLAlchemy engine, `get_session` dependency, and idempotent seed loader for `company.json`, `plans.json`, `policies.json`, `customers.json`, `handlers.json`, `claims.json`, `policy_wording.md`, and read-only agent instructions.
  - `backend/schemas.py`: Typed Pydantic request and response models.
- **Phase 2 — Backend Read, Decision, Payment & Sign-Off API**:
  - `backend/main.py`: FastAPI routes with explicit `operation_id`s (`health`, `list_claims`, `get_claim`, `get_policy`, `get_customer`, `list_handlers`, `get_policy_wording`, `get_instructions`, `record_claim_step`, `decide_claim`, `pay_claim`, `sign_off_claim`).
- **Phase 3 — The UnderCover Agent & Backend Run Trigger**:
  - `agent/main.py`: LangChain `create_agent` entry point `run(claim_id, thread_id, llm=None)` on OpenRouter (`openai/gpt-6-luna` with `reasoning_effort="low"` by default, or `MODEL_NAME`), fetching its system prompt from `GET /api/instructions` and logging step-by-step progress via tools.
  - `backend/main.py`: `POST /api/claims/{claim_id}/run` (`run_claim_agent`).
- **Phase 4 — Dashboard Foundation, Brand Theme & Claims Queue**:
  - `dashboard/index.html` & `dashboard/src/styles.css`: Nordic Obsidian & Precision Daylight theme (`Space Grotesk`, `Plus Jakarta Sans`, `Fraunces`, `Geist Mono`) with light and dark surface custom properties.
  - `dashboard/src/types.ts` & `dashboard/src/api.ts`: Strict TypeScript models and API client.
  - `dashboard/src/components/StatusBadge.tsx` & `dashboard/src/components/ClaimsQueue.tsx`: Semantic status/decision badges and filterable claims queue table with tabular USD currency columns.
- `e2e/`: Playwright smoke test
