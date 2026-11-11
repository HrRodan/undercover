# Tech stack

- `backend/`: FastAPI and SQLite (`sqlite3`). Every API operation has an `operation_id`, a one-line docstring and no optional inputs. Paying a claim is a separate operation that takes the amount. Use sqlalchemy for everything database related. Data file paths (`policy_wording_short_optimized.md`, `claims_manual.md`, and JSON seed files) are centrally configured in `backend/config.py` and overridable via environment variables.
- `agent/`: LangChain's `create_agent` on OpenRouter (`langchain-openai` + `httpx`), with a master queue agent (`run_queue` with `reasoning_effort="medium"`) that plans a to-do list and delegates each claim to a fresh claim subagent (`run` / `work_claim` with `reasoning_effort="low"`), wrapped in `@wrap_model_call` and `@wrap_tool_call` middleware and traced with `RunnableConfig`. It reaches claims, the policy wording, the claims manual, and its instructions only through the backend's API. Model names (`openai/gpt-6-luna` by default, or `MODEL_NAME` / `QUEUE_MODEL_NAME` / `CLAIM_MODEL_NAME`) and timeouts are centrally configured in `agent/config.py`.
- `dashboard/`: React 19, Vite, TypeScript and vanilla CSS with custom properties (no external CSS framework).
- `e2e/`: Playwright end-to-end tests (`@playwright/test` via `npm run e2e`), and `playwright-cli` for interactive browser checks.
- `data/`: the business data the backend starts from (`policy_wording_short_optimized.md`, `claims_manual.md`, and JSON files). The agent never sees `data/evals/` or `data/security/`.

Python 3.12 with uv, all in the root `pyproject.toml`. Node 22+ (up to Node 26). The OpenRouter key is `OPENROUTER_API_KEY` in `.env`.
