# Process

## Environment & Checks

`uv sync` and `npm install` at the repo root install all dependencies, including the `lefthook` git pre-commit hook. `npm run dev` starts the backend and the dashboard concurrently.

`npm run check` runs the full verification suite:

- **Python (`npm run check:python`)**: `ruff format --check`, `ruff check`, `pyright`, and `pytest` with `>= 80%` coverage across `backend/` and `agent/`
- **TypeScript (`npm run check:ts`)**: `prettier --check`, `eslint`, `tsc`, and `vitest` with `>= 80%` coverage in `dashboard/`
- **End-to-End (`npm run e2e`)**: Playwright tests (`@playwright/test`) in `e2e/`

The pre-commit hook runs format, lint, type, and unit test checks automatically on every commit.

## Workflow: Plan Then Implement

Work follows a two-step cycle with review in between (or clarify upfront if requirements are ambiguous):

### 1. Planning

When asked to plan (for example, *"Please plan the pilot"* or *"Please plan <the work> in docs/<NAME>.md"*), write the plan to `docs/PLAN.md` (or `docs/PLAN_<NAME>.md`) and **write no code**.

- Split the work into 5 or 6 ordered phases, each building cleanly on the last.
- Explain what each phase builds, the files and modules affected, and why you chose that approach.
- Give each phase explicit, verifiable success criteria written as checkboxes (`- [ ]`):
  - Unit, API, component, and E2E tests that must pass
  - Commands to run and their expected output
  - API calls and their expected responses
  - UI states and pages to verify in the browser with `playwright-cli`
- Stop and wait for approval before implementing.

### 2. Implementing

When asked to implement a plan (for example, *"Please implement the plan for the pilot"*), execute every phase in order without stopping. For each phase:

1. **Build & Test:** Implement the phase following `docs/CODE_STANDARDS.md`, including unit, API/component, and E2E tests as appropriate.
2. **Verify:** Check every success criterion for the phase (run the test suite, verify API responses, and inspect pages with `playwright-cli`). Fix any failure at its root cause before moving on; if an approach fails, re-evaluate rather than forcing a workaround.
3. **Document Progress:** Tick off the completed checkboxes (`- [x]`) in the plan document and update `docs/STATUS.md` (and `README.md` if applicable).
4. **Commit:** Commit the completed phase. The pre-commit hook runs automatically; if any check fails, fix the issue and commit again.

When the final phase is complete, run `npm run check` and report the verification results.

## Ad-Hoc Changes & Questions

For smaller tasks outside a multi-phase build plan:

- Clarify first if the request is ambiguous or has significant architectural tradeoffs; otherwise keep responses concise and focused.
- Verify changes with relevant tests and `npm run check`, update `docs/STATUS.md` if behavior changed, and commit once verified.

## Rules

- **Test every change:** Include tests with every feature or fix (Python `pytest` for backend/agent, `vitest` for dashboard components, and `@playwright/test` for end-to-end flows).
- **Never call a live LLM in tests:** Always inject or stub the model in tests (`BaseChatModel` stub or fake).
- **Protect the eval set:** Never open or expose `data/evals/` to the agent or read it unless explicitly asked.
- **No shortcuts on quality gates:**
  - Never use `git commit --no-verify`.
  - Never lower a coverage threshold, disable a linter rule, or exclude files to force a green run. If a rule blocks valid work, stop and ask.
- **Keep `docs/STATUS.md` current:** Update it whenever routes, tools, UI capabilities, or run instructions change.
- **Never push:** Leave `git push` to the user unless explicitly asked.
- **Cross-platform scripts:** Everything in `package.json` must work on Windows, macOS, and Linux—write scripts using `uv run`, cross-platform CLIs, or `.mjs` scripts rather than bash-only syntax.
