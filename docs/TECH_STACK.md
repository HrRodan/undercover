# Tech stack

- `backend/`: FastAPI and SQLite (`sqlite3`). Every API operation has an `operation_id`, a one-line docstring and no optional inputs. Paying a claim is a separate operation that takes the amount. Use sqlalchemy for everything database related.
- `agent/`: LangChain's `create_agent` on OpenRouter (`langchain-openai` + `httpx`), with one entry point that takes a claim id and a thread id. It reaches claims and its instructions only through the backend's API. It uses `openai/gpt-6-luna` with low reasoning effort by default, or the model in the environment variable `MODEL_NAME` if set, such as `openrouter/free`.
- `dashboard/`: React 19, Vite, TypeScript and vanilla CSS with custom properties (no external CSS framework).
- `e2e/`: Playwright end-to-end tests (`@playwright/test` via `npm run e2e`), and `playwright-cli` for interactive browser checks.
- `data/`: the business data the backend starts from. The agent never sees `data/evals/`, which holds the answer key.

Python 3.12 with uv, all in the root `pyproject.toml`. Node 22+ (up to Node 26). The OpenRouter key is `OPENROUTER_API_KEY` in `.env`.
