# UnderCover Agent Harness Implementation Plan

## Goal

Build the UnderCover Agent Harness described in `docs/HARNESS.md`: a two-tier LangChain + LangGraph agent architecture (`create_agent`, custom middleware hooks, LangGraph state/persistence, and LangChain runnable tracing) where a queue master agent (`openai/gpt-6-luna` / `luna-latest` with `reasoning_effort="medium"`) plans and manages a live to-do list, delegates each claim via a `work_claim` subagent tool to a fresh single-claim subagent (`reasoning_effort="low"`), looks up sections of both the Policy Wording (`policy_wording_short_optimized.md` by default) and the Claims Handling Manual (`claims_manual.md` by default) on demand, automatically recovers from tool/model/claim errors (retrying failed claims once and leaving twice-failed claims for a handler without double-deciding or double-paying), checks for missed waiting claims within an optional cap, and surfaces the live to-do list, run summary, dual instructions, and read document sections in the React dashboard.

## Architecture Overview

- **Centralized Harness & Document Configuration (`backend/config.py` & `agent/config.py`)**:
  - All runtime parameters—model names, reasoning effort levels, timeouts, retry counts, and the exact data files used (`policy_wording_short_optimized.md` by default)—are centralized in typed configuration objects backed by environment variables with sensible defaults:
    - **Backend Document & Seed Config (`backend/config.py`)**:
      - `POLICY_WORDING_FILE` (env `UNDERCOVER_POLICY_WORDING_FILE`, default `"policy_wording_short_optimized.md"`)
      - `CLAIMS_MANUAL_FILE` (env `UNDERCOVER_CLAIMS_MANUAL_FILE`, default `"claims_manual.md"`)
      - `CLAIMS_FILE` (env `UNDERCOVER_CLAIMS_FILE`, default `"claims.json"`)
      - `POLICIES_FILE` (env `UNDERCOVER_POLICIES_FILE`, default `"policies.json"`)
      - `CUSTOMERS_FILE` (env `UNDERCOVER_CUSTOMERS_FILE`, default `"customers.json"`)
      - `PLANS_FILE` (env `UNDERCOVER_PLANS_FILE`, default `"plans.json"`)
      - `HANDLERS_FILE` (env `UNDERCOVER_HANDLERS_FILE`, default `"handlers.json"`)
      - `COMPANY_FILE` (env `UNDERCOVER_COMPANY_FILE`, default `"company.json"`)
      - Exposed via `GET /api/config` (`operation_id="get_config"`) so the agent and dashboard can inspect the active model and document file configuration.
    - **Agent Model & Harness Config (`agent/config.py`)**:
      - `MODEL_NAME` (env `MODEL_NAME`, default `"openai/gpt-6-luna"`)
      - `QUEUE_MODEL_NAME` (env `QUEUE_MODEL_NAME`, falls back to `MODEL_NAME`)
      - `CLAIM_MODEL_NAME` (env `CLAIM_MODEL_NAME`, falls back to `MODEL_NAME`)
      - `QUEUE_REASONING_EFFORT` (env `QUEUE_REASONING_EFFORT`, default `"medium"`)
      - `CLAIM_REASONING_EFFORT` (env `CLAIM_REASONING_EFFORT`, default `"low"`)
      - `OPENROUTER_BASE_URL` (env `OPENROUTER_BASE_URL`, default `"https://openrouter.ai/api/v1"`)
      - `MODEL_TIMEOUT_SECONDS` (env `MODEL_TIMEOUT_SECONDS`, default `120`)
      - `MODEL_MAX_RETRIES` (env `MODEL_MAX_RETRIES`, default `3`)
      - `DEFAULT_RECURSION_LIMIT` (env `AGENT_RECURSION_LIMIT`, default `200`)
- **LangChain & LangGraph Harness (`agent/`)**:
  - **Two-Tier `create_agent` Hierarchy with Full Ecosystem Tracing**:
    - **Master Queue Agent (`run_queue`)**: Built with `langchain.agents.create_agent`, `InMemorySaver` checkpointer, and custom LangChain middleware (`@wrap_model_call`, `@wrap_tool_call`, `@after_model`). Uses `agent.config` (`QUEUE_MODEL_NAME` with `QUEUE_REASONING_EFFORT="medium"`). Configured with `RunnableConfig` (`run_name="undercover_queue_agent"`, `tags=["queue-agent", "harness"]`, `metadata={"thread_id": ..., "cap": ...}`, `recursion_limit=200`) so every master turn, tool call, and subagent delegation is linked in a single trace tree.
    - **Single-Claim Subagent (`run` / `work_claim`)**: Invoked either directly for one named claim (`run(claim_id, thread_id, llm=...)`) or delegated from the master agent's `@tool def work_claim(claim_id: str, config: RunnableConfig) -> str`. Each subagent invocation creates a fresh `create_agent` instance with an isolated `thread_id` (`f"{parent_thread_id}-claim-{claim_id}-attempt-{attempt}"`) and passes the parent `RunnableConfig` callbacks/metadata so LangSmith/LangChain tracing nests the subagent's full tool loop under the parent `work_claim` tool span while keeping the LLM message context completely clean. Uses `CLAIM_MODEL_NAME` with `CLAIM_REASONING_EFFORT="low"`.
  - **Middleware & Automatic Recovery**:
    - **Model Retry & Timeout Middleware (`@wrap_model_call`)**: Wraps model invocations with configurable retry logic so transient OpenRouter or provider errors do not crash a run.
    - **Tool Error Boundary & Step-Logging Middleware (`@wrap_tool_call`)**: Intercepts tool execution inside `create_agent`, automatically logs progress steps to the backend (`POST /api/claims/{claim_id}/steps`), and converts unexpected HTTP/validation exceptions into structured tool error messages (`ToolMessage`) so the LLM can recover or the harness can cleanly unwind.
    - **Claim-Level Failure & Retry Lifecycle**: In `work_claim`, if a subagent run raises an unrecoverable exception or finishes without recording a decision (`status == "in_progress"` and `decision is None`), the harness calls `POST /api/claims/{claim_id}/fail`:
      - After **1st failure**: `attempts` becomes `1`, the claim status resets from `in_progress` back to `waiting`, and `work_claim` returns a one-line failure report instructing the queue agent to retry the claim.
      - After **2nd failure**: `attempts` becomes `2`, the claim status becomes `left_for_handler`, the to-do item is marked `left_for_handler`, and `work_claim` reports that the claim has failed twice and been left for a handler.
    - **Idempotency Guard**: Neither `work_claim` nor `decide_claim` / `pay_claim` can decide or pay an already-decided claim twice (`409 Conflict` if a claim is already `decided` or `waiting_for_sign_off`, which `work_claim` checks upfront before starting a subagent).
    - **Cap & Missed-Claim Verification**: The queue agent's `get_waiting_claims` tool respects the run's `cap` (selecting up to `cap` waiting claims for the run scope) and a `check_missed_claims` tool (plus post-loop verification) ensures no waiting claim within the capped target set is left behind in `waiting` or `in_progress` before the run finishes.
  - **CLI Entry Point (`agent/__main__.py`)**: Supports `uv run -m agent`, `uv run -m agent --cap 5`, and `uv run -m agent --claim CLM-1001`.
- **Backend (`backend/`)**:
  - **Claims Manual & Section Lookup API**: Seeds `data/claims_manual.md` (`ClaimsManualRecord`) alongside `data/policy_wording_short_optimized.md` (`PolicyWordingRecord`), controlled by `backend/config.py`. Parses markdown `## ` headings (both unnumbered headings like `## Limits`, `## Trip Delay`, `## Baggage` in `policy_wording_short_optimized.md` and numbered headings like `## 4. Working a claim`, `## 7. Interpretation notes` in `claims_manual.md`) to expose section listing, keyword search, and single-section retrieval endpoints (`GET /api/claims-manual`, `GET /api/documents/{doc_name}/sections`, `GET /api/documents/{doc_name}/sections/{section_id}`, `GET /api/documents/search?query=...`).
  - **To-Do List & Queue Run State (`TodoItemRecord`, `QueueRunRecord`)**: Stores the current run's to-do list (`claim_id`, `description`, `status`: `to_do` | `in_progress` | `done` | `left_for_handler`, `result_summary`) and run status/summary (`status`, `cap`, `summary`), exposed via `GET /api/todos`, `PUT /api/todos`, `GET /api/queue-run`, and `POST /api/queue/run`.
  - **Claim Attempt Tracking & `left_for_handler` Status**: Adds `attempts` (`int`, default `0`) and `sections_read_json` (`list[str]`) to `ClaimRecord`. Adds `POST /api/claims/{claim_id}/fail` to handle 1st-failure reset (`status = "waiting"`) vs 2nd-failure escalation (`status = "left_for_handler"`), and hardens `decide_claim` / `pay_claim` so a decided or paid claim cannot be decided or paid a second time.
  - **Dual Instructions (`InstructionsRecord`)**: Serves both `queue_instructions` (for the master queue agent) and `claim_instructions` (for the single-claim subagent, written from the Policy Wording and Claims Manual) at `GET /api/instructions`.
- **Dashboard (`dashboard/`)**:
  - **Queue Run Controls & Cap Input**: Allows handlers to run the whole queue or start a run capped at $N$ claims (e.g., 5 claims or all waiting), plus run a single claim on its detail page.
  - **Live To-Do List & Run Summary Panel**: Displays the master agent's live to-do list (`to_do`, `in_progress`, `done`, `left_for_handler`) and its final handover summary on the queue workspace.
  - **Claim Detail Document Sections Read**: Displays the specific sections of the Policy Wording and Claims Handling Manual that the subagent looked up and read while evaluating the claim, plus the `Left for handler` badge when a claim fails twice.
  - **Instructions Screen**: Displays both the Queue Agent Instructions and the Claim Subagent Instructions alongside the Policy Wording (`policy_wording_short_optimized.md`) and Claims Handling Manual (`claims_manual.md`) reference views.

---

## Phase 1: Centralized Configuration, Database Schema, Manual Seeding & Section Lookup API

### What This Phase Builds

1. Creates `backend/config.py` and `agent/config.py` to centralize all configurable parameters:
   - `backend/config.py`: configurable data directory and exact filenames (`POLICY_WORDING_FILE = "policy_wording_short_optimized.md"`, `CLAIMS_MANUAL_FILE = "claims_manual.md"`, `CLAIMS_FILE = "claims.json"`, `POLICIES_FILE = "policies.json"`, `CUSTOMERS_FILE = "customers.json"`, `PLANS_FILE = "plans.json"`, `HANDLERS_FILE = "handlers.json"`, `COMPANY_FILE = "company.json"`), each overridable via environment variables (`UNDERCOVER_POLICY_WORDING_FILE`, `UNDERCOVER_CLAIMS_MANUAL_FILE`, etc.).
   - `agent/config.py`: configurable model names (`MODEL_NAME`, `QUEUE_MODEL_NAME`, `CLAIM_MODEL_NAME`, defaulting to `"openai/gpt-6-luna"`), reasoning efforts (`QUEUE_REASONING_EFFORT = "medium"`, `CLAIM_REASONING_EFFORT = "low"`), timeouts, retries, and recursion limits.
2. Extends the SQLAlchemy 2.x ORM models, seed loader, and FastAPI routes to:
   - Seed `CLAIMS_MANUAL_FILE` (`ClaimsManualRecord`) and `POLICY_WORDING_FILE` (`PolicyWordingRecord`), plus dual agent instructions (`queue_instructions` and `claim_instructions`).
   - Parse markdown `## ` sections in both `policy_wording_short_optimized.md` (unnumbered headings such as `Limits`, `Cancellation and Interruption`, `Trip Delay`, `Baggage Delay`, `Baggage`, `Passport`, `Emergency Medical`, `Add-ons`, `Never covered`, `Payment`, `Claims`) and `claims_manual.md` (numbered headings `1` through `14`), allowing lookup by section index, slug, or title, as well as keyword search across both documents.
   - Track claim `attempts`, `sections_read`, and the `left_for_handler` status on `ClaimRecord`, and persist the active queue run's to-do list (`TodoItemRecord`) and run summary (`QueueRunRecord`).
   - Enforce idempotency on `POST /api/claims/{claim_id}/decision` and `POST /api/claims/{claim_id}/pay` so no claim is ever decided or paid twice, and add `POST /api/claims/{claim_id}/fail` to put a failed claim back in `waiting` on the first failure and mark it `left_for_handler` on the second failure.

### Files Affected

- Create: `backend/config.py` (centralized configuration for exact data files and backend settings)
- Create: `agent/config.py` (centralized configuration for model names, reasoning effort levels, timeouts, retries, and recursion limit)
- Modify: `backend/models.py` (add `ClaimsManualRecord`, `TodoItemRecord`, `QueueRunRecord`; add `attempts` and `sections_read_json` to `ClaimRecord`; add `queue_instructions` and `claim_instructions` to `InstructionsRecord`)
- Modify: `backend/schemas.py` (add schemas for config, document sections, search results, claims manual, to-do list items, queue run request/status, failure recording, and dual instructions)
- Modify: `backend/db.py` (use `backend/config.py` for seeding `policy_wording_short_optimized.md` and `claims_manual.md`, implement markdown section parser/searcher, add to-do list and queue-run persistence, implement `fail_claim_attempt`, and block duplicate decisions/payments)
- Modify: `backend/main.py` (add routes for `GET /api/config`, `GET /api/claims-manual`, document section listing/reading/searching, to-do list `GET`/`PUT`, and `POST /api/claims/{claim_id}/fail`)
- Modify: `backend/tests/test_db.py` and `backend/tests/test_api.py` (unit and API tests for configurable files, manual seeding, section lookup/search on `policy_wording_short_optimized.md` and `claims_manual.md`, to-do list storage, duplicate decision/payment rejection, and 1st/2nd failure transitions)

### Why This Approach

Centralizing file paths in `backend/config.py` and model/reasoning parameters in `agent/config.py` makes it trivial to swap `policy_wording_short_optimized.md`, `policy_wording_optimized.md`, or `policy_wording.md` (or switch models and reasoning efforts) via a single config setting or environment variable without touching business logic. Parsing `## ` headings supports both the concise unnumbered headings in `policy_wording_short_optimized.md` and the numbered headings in `claims_manual.md`, so the agent can look up sections by number (`"1"`, `"7"`), slug/title (`"Baggage"`, `"Trip Delay"`, `"Interpretation notes"`), or keyword search.

### Success Criteria

- [x] `backend/config.py` defaults `POLICY_WORDING_FILE` to `"policy_wording_short_optimized.md"` and `CLAIMS_MANUAL_FILE` to `"claims_manual.md"`, and `GET /api/config` returns the active file and model configuration.
- [x] `backend/tests/test_db.py` verifies that `init_db()` seeds `data/claims_manual.md` (Version `2026.2`), `data/policy_wording_short_optimized.md` (Version `2026.1`), and both `queue_instructions` and `claim_instructions`, while never reading `data/evals/` or `data/security/`.
- [x] `GET /api/claims-manual` returns `{ "version": "2026.2", "content": "# UnderCover Claims Handling Manual..." }`.
- [x] `GET /api/documents/policy_wording/sections` returns the sections from `policy_wording_short_optimized.md` (`Limits`, `Cancellation and Interruption`, `Trip Delay`, `Baggage Delay`, `Baggage`, `Passport`, `Emergency Medical`, `Add-ons`, `Never covered`, `Payment`, `Claims`) and `GET /api/documents/claims_manual/sections` returns the 14 sections from `claims_manual.md`.
- [x] `GET /api/documents/claims_manual/sections/7?claim_id=CLM-1020` and `GET /api/documents/policy_wording/sections/Baggage?claim_id=CLM-1020` return the requested sections, record the section titles in `CLM-1020`'s `sections_read` list, and append steps on `CLM-1020`.
- [x] `GET /api/documents/search?query=monkey` returns matching sections from the manual/wording.
- [x] `GET /api/instructions` returns `instructions` (combined), `queue_instructions`, and `claim_instructions`.
- [x] `PUT /api/todos` stores the ordered to-do items (`claim_id`, `description`, `status`, `result_summary`) and `GET /api/todos` returns them.
- [x] Calling `POST /api/claims/CLM-1001/fail` once increments `attempts` to `1` and puts the claim back in `status = "waiting"`. Calling `POST /api/claims/CLM-1001/fail` a second time increments `attempts` to `2` and sets `status = "left_for_handler"`.
- [x] Calling `POST /api/claims/CLM-1001/decision` or `POST /api/claims/CLM-1001/pay` on a claim that is already decided or paid returns HTTP `409 Conflict`.
- [x] Command `uv run pytest backend/tests/ -q` passes with `>= 80%` coverage.

---

## Phase 2: Subagent Harness, Document Lookup Tools & LangChain Middleware

### What This Phase Builds

Upgrades the single-claim agent in `agent/main.py` into a modular, middleware-wrapped LangChain subagent (`create_claim_subagent` / `run`) powered by `agent/config.py`:
1. **Configurable Model Factory (`model(role="claim", reasoning_effort=...)`)**: Uses `agent.config` to build `ChatOpenAI` for either `"queue"` (`QUEUE_MODEL_NAME`, `QUEUE_REASONING_EFFORT="medium"`) or `"claim"` (`CLAIM_MODEL_NAME`, `CLAIM_REASONING_EFFORT="low"`), with configurable timeout and retries.
2. **Section-Based Document Tools**:
   - `list_document_sections(doc_name: str)` — lists section IDs and titles in `policy_wording` or `claims_manual`.
   - `search_documents(query: str)` — searches across both `policy_wording` and `claims_manual` for matching sections.
   - `read_document_section(doc_name: str, section_id: str)` — fetches only the requested section of the Policy Wording or Claims Manual and records the read section on the active claim (`sections_read` and `steps`).
3. **LangChain Middleware (`langchain.agents.middleware`)**:
   - `@wrap_model_call` middleware (`model_retry_middleware`) that catches transient model/provider timeouts or API errors and retries up to `MODEL_MAX_RETRIES` before propagating.
   - `@wrap_tool_call` middleware (`tool_guard_middleware`) that catches tool HTTP/validation errors and returns structured error messages so a single bad tool call does not crash the agent loop, and prevents calling `decide_claim` or `pay_claim` twice on the same claim.
4. **Instructions Crafted from Wording & Manual**: Updates `claim_instructions` in `backend/db.py` to guide the subagent to inspect the claim, policy, and customer history, look up the relevant sections of the Policy Wording (`policy_wording_short_optimized.md`) and Claims Manual (`claims_manual.md`), apply manual rules (3rd claim in 12 months referral, wild animal accidental loss/damage, $35/day unreceipted Trip Delay meals, $350/night accommodation cap, story vs. document conflict referral to SIU), and return a concise one-line summary (`"<claim_id>: <decision> ($<payout>)"`).

### Files Affected

- Modify: `agent/main.py` (use `agent/config.py`, add `model(role=..., reasoning_effort=...)`, `list_document_sections`, `search_documents`, `read_document_section`, `@wrap_model_call` and `@wrap_tool_call` middleware, and tracing metadata in `RunnableConfig`)
- Modify: `backend/db.py` (update `CLAIM_INSTRUCTIONS` and `QUEUE_INSTRUCTIONS` derived strictly from `data/policy_wording_short_optimized.md` and `data/claims_manual.md`)
- Modify: `agent/tests/test_agent.py` (unit tests with `StubModel` testing `agent/config.py`, section lookup tools, middleware error recovery, `reasoning_effort` configuration, and recording read sections on the claim)

### Why This Approach

Using LangChain's `create_agent` with `@wrap_model_call` and `@wrap_tool_call` middleware keeps the subagent architecture idiomatic to the LangChain 1.x / LangGraph ecosystem while providing deterministic guardrails around every model call and tool invocation. Passing `RunnableConfig` with `run_name="undercover_claim_subagent"`, `tags=["claim-subagent", claim_id]`, and `metadata={"claim_id": claim_id, "attempt": ...}` gives full observability in LangSmith / LangChain callbacks.

### Success Criteria

- [x] `agent.main.model("queue")` configures `reasoning_effort="medium"` and `agent.main.model("claim")` configures `reasoning_effort="low"` using `agent/config.py` (and honors environment overrides `MODEL_NAME`, `QUEUE_MODEL_NAME`, `CLAIM_MODEL_NAME`, `QUEUE_REASONING_EFFORT`, `CLAIM_REASONING_EFFORT`).
- [x] Subagent tools `list_document_sections`, `search_documents`, and `read_document_section` retrieve sections from `policy_wording` (`policy_wording_short_optimized.md`) and `claims_manual` (`claims_manual.md`) via the backend API and record the read sections on the claim (`sections_read` and `steps`).
- [x] Unit tests in `agent/tests/test_agent.py` verify that `@wrap_tool_call` middleware catches a failing tool call and returns a structured error message without crashing the subagent.
- [x] Unit tests verify that `@wrap_model_call` middleware retries a transient model error and succeeds on the next attempt.
- [x] Command `uv run pytest agent/tests/test_agent.py -q` passes with zero live LLM calls.

---

## Phase 3: Master Queue Agent, Subagent Delegation, To-Do List & Auto-Recovery

### What This Phase Builds

Implements the Master Queue Agent (`run_queue(thread_id: str, cap: int | None = None, llm: BaseChatModel | None = None, subagent_llm: BaseChatModel | None = None) -> str`) and CLI entry point (`agent/__main__.py`):
1. **Queue Orchestration Tools**:
   - `get_waiting_claims()` — fetches waiting claims from `GET /api/claims`, applies the active run's target `cap` (locking the target claim IDs for the run so only those up to `cap` are worked and the rest stay `waiting`), and returns their summaries (`claim_id`, `claim_type`, `amount_claimed`, `summary`, `attempts`).
   - `write_todos(todos: list[dict[str, str]])` — updates the live to-do list on the backend (`PUT /api/todos`) with each item's `claim_id`, `description`, `status` (`to_do`, `in_progress`, `done`, `left_for_handler`), and `result_summary`.
   - `work_claim(claim_id: str, config: RunnableConfig)` — spawns a fresh single-claim subagent (`run(claim_id, sub_thread_id, llm=subagent_llm, parent_config=config)`) with a clean message history and `reasoning_effort="low"`, propagating LangChain callbacks/tracing from `config`:
     - Before running, verifies the claim is in the run's allowed set and not already decided/paid (`status in ("decided", "waiting_for_sign_off")`), preventing any double decision or payment.
     - Automatically marks the claim's to-do item `in_progress` before starting.
     - If the subagent decides the claim (`decided` or `waiting_for_sign_off`), updates the to-do item to `done` and returns a one-line report: `f"{claim_id}: {decision} (${payout:,.2f}) — {status}"`.
     - If the subagent raises an exception or finishes without recording a decision, calls `POST /api/claims/{claim_id}/fail`:
       - On **1st failure** (`attempts == 1`): claim status returns to `waiting`, to-do item returns to `to_do`, and `work_claim` returns `f"{claim_id}: failed on attempt 1 ({error}); returned to waiting queue to retry."`
       - On **2nd failure** (`attempts >= 2`): claim status becomes `left_for_handler`, to-do item becomes `left_for_handler`, and `work_claim` returns `f"{claim_id}: failed twice ({error}); left for a handler."`
   - `check_missed_claims()` — checks the backend to confirm whether any claim in the run's capped target set is still `waiting` or `in_progress`. Returns `"All target claims accounted for."` or lists the remaining claim IDs that must be worked before finishing.
2. **Harness Finalization & Safety Net**:
   - Uses `InMemorySaver` checkpointer on the master agent so its state and thread history are persisted under `thread_id`.
   - After the master agent's `create_agent` loop completes (or if the model stops early), the harness runs a deterministic verification pass over the run's target claims so any claim still stuck or missed within the cap is retried/reconciled, ensuring 100% compliance with requirement 5 (*"One bad claim must never stop the run or leave a claim stuck in progress... Before it finishes, the agent checks that it has not missed a waiting claim within its cap"*).
   - Stores the master agent's final handover summary on the queue run record (`POST /api/queue/run` / `PUT /api/queue-run`).
3. **Backend Queue Run Endpoints & CLI**:
   - Adds `POST /api/queue/run` (`operation_id="run_claims_queue"`) taking `QueueRunRequest(cap: int)` (where `cap` is the maximum number of waiting claims to work, e.g., `25` for all waiting or `5` for a 5-claim trial, keeping zero optional inputs per `docs/CODE_STANDARDS.md`).
   - Adds `agent/__main__.py` supporting `uv run -m agent`, `uv run -m agent --cap 5`, and `uv run -m agent --claim CLM-1001`.

### Files Affected

- Modify: `agent/main.py` (implement `get_waiting_claims`, `write_todos`, `work_claim`, `check_missed_claims`, `run_queue`, and parent-to-subagent `RunnableConfig` trace propagation)
- Create: `agent/__main__.py` (CLI runner supporting `--cap` and `--claim`)
- Modify: `backend/main.py` (add `POST /api/queue/run`, `GET /api/queue-run`, `GET /api/todos`, `PUT /api/todos`)
- Modify: `agent/tests/test_agent.py` and `backend/tests/test_api.py` (comprehensive tests with `StubModel` for queue run, to-do list updates, `cap` enforcement, 1st failure retry, 2nd failure `left_for_handler`, idempotency against double decision/payment, and missed-claim check)

### Why This Approach

Giving `POST /api/queue/run` a required `cap: int` field in `QueueRunRequest(cap: int)` satisfies `docs/CODE_STANDARDS.md` (every route has an explicit `operation_id`, a one-line docstring, and no optional inputs) while supporting both full queue runs (`cap=25`) and capped trial runs (`cap=5`). Propagating `RunnableConfig` callbacks and metadata from `run_queue` into `work_claim` ensures LangSmith / LangChain tracing captures the entire master-agent -> subagent execution hierarchy.

### Success Criteria

- [x] Unit test with `StubModel`: `run_queue` plans a to-do list via `write_todos`, delegates each claim via `work_claim` to a fresh subagent, updates each to-do item to `done`, verifies `check_missed_claims`, and returns a summary for handlers.
- [x] Unit test with `StubModel`: `run_queue(thread_id="t-cap", cap=2, ...)` works only 2 waiting claims and leaves the other 23 claims in `waiting` status.
- [x] Unit test with `StubModel`: when a claim subagent fails on its first attempt, the run does not stop; the claim goes back to `waiting` (`attempts == 1`), is retried on a second `work_claim` call, and succeeds.
- [x] Unit test with `StubModel`: when a claim fails twice (`attempts == 2`), it is marked `left_for_handler` (and its to-do item is `left_for_handler`), is not tried a third time, and the rest of the queue run finishes normally.
- [x] Unit test with `StubModel`: attempting to decide or pay an already-decided claim is blocked so no claim is ever decided or paid twice.
- [x] Unit test with `StubModel`: if the queue agent overlooks a waiting claim within its `cap`, `check_missed_claims` / the harness verification catches it and processes it before finishing.
- [x] Command `npm run check:python` passes `ruff format --check`, `ruff check`, `pyright`, and `pytest` with `>= 80%` coverage.

---

## Phase 4: Dashboard To-Do List, Capped Queue Run, Sections Read & Dual Instructions UI

### What This Phase Builds

Updates the React 19 + TypeScript dashboard in `dashboard/` to surface all new harness capabilities while adhering strictly to `docs/BRAND.md` and `docs/CODE_STANDARDS.md`:
1. **Queue Page To-Do List & Run Summary (`TodoListPanel.tsx` & `ClaimsQueue.tsx`)**:
   - Adds a cap selector/input alongside the queue run button so handlers can run all waiting claims or cap a trial run (e.g., 5 claims).
   - Displays the live **Agent To-Do List** for the current run on the queue page, showing each item's status badge (`To do`, `In progress`, `Done`, `Left for handler`) and one-line subagent outcome, plus the master agent's handover summary when the run finishes.
   - Adds the `Left for handler` status filter tab and metric count on `ClaimsQueue` and semantic badge (`badge-rose` / `badge-amber`) in `StatusBadge.tsx`.
2. **Claim Detail Sections Read (`ClaimDetail.tsx`)**:
   - Shows the **Policy Wording & Manual Sections Read** on the claim page so handlers can see exactly which sections of the Policy Wording and Claims Manual the subagent looked up for that claim, alongside the step-by-step trace.
3. **Dual Instructions & Claims Manual View (`InstructionsView.tsx`)**:
   - Displays both the **Queue Agent Instructions** (for running the queue) and the **Claim Subagent Instructions** (for working a claim), as well as the **Policy Wording** (`policy_wording_short_optimized.md`) and **Claims Handling Manual** (`claims_manual.md`) reference documents.

### Files Affected

- Modify: `dashboard/src/types.ts` (add `"left_for_handler"` to `ClaimStatus`, `sections_read` and `attempts` to `ClaimDetail`, `TodoItem`, `QueueRunState`, `ClaimsManualResponse`, and `queue_instructions` / `claim_instructions` to `InstructionsResponse`)
- Modify: `dashboard/src/api.ts` (add client functions for `POST /api/queue/run`, `GET /api/todos`, `GET /api/queue-run`, and `GET /api/claims-manual`)
- Modify: `dashboard/src/components/StatusBadge.tsx` (add `left_for_handler` status badge and `TodoStatusBadge`)
- Create: `dashboard/src/components/TodoListPanel.tsx` (renders the current run's live to-do list and handover summary)
- Modify: `dashboard/src/components/ClaimsQueue.tsx` (add cap control, `Left for handler` filter tab, and embed `TodoListPanel`)
- Modify: `dashboard/src/components/ClaimDetail.tsx` (render the list of Policy Wording and Claims Manual sections read by the agent on the claim)
- Modify: `dashboard/src/components/InstructionsView.tsx` (render both Queue Agent Instructions and Claim Subagent Instructions, plus the Policy Wording and Claims Handling Manual reference panels)
- Modify: `dashboard/src/App.tsx` (wire queue run with cap, poll `/api/todos` and `/api/queue-run` during active runs, and pass manual/instructions data)
- Modify: `dashboard/src/styles.css` (add clean styling for the to-do list panel, cap input control, and read-sections pills using existing CSS custom properties)
- Modify: `dashboard/src/App.test.tsx` (add Vitest component tests for the to-do list display, capped queue run trigger, `left_for_handler` state, read sections on the claim detail view, and dual instructions view)

### Why This Approach

Splitting the to-do list into a focused `TodoListPanel.tsx` component keeps `ClaimsQueue.tsx` and `App.tsx` concise and well within the ESLint complexity and line limits (`max 200 lines per function`, `max 500 lines per file`, `complexity <= 15`). Polling `GET /api/todos`, `GET /api/queue-run`, and `GET /api/claims` together while a run is active updates the to-do list, claim statuses, and step logs in real time without layout shift.

### Success Criteria

- [x] Vitest tests in `dashboard/src/App.test.tsx` verify:
  - The queue page renders the current run's to-do list with items in `To do`, `In progress`, `Done`, and `Left for handler` states, plus the run summary.
  - Starting a queue run with a cap sends `POST /api/queue/run` with `{ "cap": 5 }`.
  - Selecting a claim displays the Policy Wording and Claims Manual sections the agent read on that claim.
  - Switching to the `Agent Instructions` screen displays both the Queue Agent instructions and the Claim Subagent instructions, plus the Policy Wording and Claims Manual.
- [x] Command `npm run check:ts` passes `prettier --check`, `eslint`, `tsc`, and `vitest` with `>= 80%` coverage.

---

## Phase 5: End-to-End Playwright Verification, Capped Live Trial & Documentation Update

### What This Phase Builds

1. Updates the Playwright E2E test suite (`e2e/health.spec.ts`) to test the new harness features end-to-end in the browser: the to-do list on the queue page, the sections read on the claim detail page, the `Left for handler` status when a claim fails twice, and the dual instructions on the instructions page.
2. Updates `docs/SPEC.md` (moving the claims manual from "Not for now" into the active specification as requested in `docs/HARNESS.md`), `docs/TECH_STACK.md` (documenting the configurable model and files in `backend/config.py` and `agent/config.py`, `openai/gpt-6-luna` / `luna-latest` with medium/low reasoning, and the queue/subagent architecture), and `docs/STATUS.md` (describing all new endpoints, tools, configuration variables, CLI flags, and UI views).
3. Reseeds the database and runs a live trial capped at 5 claims (`uv run -m agent --cap 5` or via the dashboard) on the default model (when `OPENROUTER_API_KEY` is configured) and verifies the live UI with `playwright-cli`.

### Files Affected

- Modify: `e2e/health.spec.ts` (add E2E assertions for the to-do list, document section lookup/display, `left_for_handler` state after two failures, and dual instructions page)
- Modify: `docs/SPEC.md` (include the claims manual in the active product specification and remove it from "Not for now")
- Modify: `docs/TECH_STACK.md` (update agent and backend description for configurable files, queue agent + claim subagent, medium/low reasoning, and claims manual tools)
- Modify: `docs/STATUS.md` (document the complete Week 1 Day 5 harness build, configuration options, and how to run it)

### Why This Approach

Testing both deterministic API-driven states in Playwright (`npm run e2e`) and a capped 5-claim run after reseeding ensures the harness meets every acceptance criterion in `docs/HARNESS.md` ("What done looks like") while keeping API trial cost minimal.

### Success Criteria

- [x] Playwright E2E suite (`npm run e2e`) passes completely, verifying the queue to-do list, claim sections read, two-failure `left_for_handler` transition, over-$1,000 sign-off, and dual instructions view.
- [x] After reseeding (`npm run db:reset`), running a 5-claim capped run works 5 claims, populates and ticks off the to-do list, records each claim's steps and read sections, and leaves the remaining 20 claims in `waiting`.
- [x] Interactive browser check with `playwright-cli` confirms the to-do list, claim steps, read sections, and instructions render cleanly in light and dark modes with zero console errors.
- [x] `docs/SPEC.md`, `docs/TECH_STACK.md`, and `docs/STATUS.md` accurately describe the product as it now is.
- [x] Command `npm run check` (`npm run check:python && npm run check:ts && npm run e2e`) passes with zero errors.
