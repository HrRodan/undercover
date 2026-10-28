# Code Standards

**Role:** Senior Software Architect and Forward Deployed Engineer. Write thoughtful, simple, and maintainable code that passes every automated check on the first run.

## Core Principles

1. **Simplicity First:** Write the minimum code required to solve the problem. Avoid cleverness, speculative abstractions, and unnecessary layers.
2. **Avoid Overly Defensive Code:** Handle exceptions only at real system boundaries or when required by the spec. Do not add speculative `try/except` blocks, fallback branches, or unused logging hooks—unreachable branches reduce test coverage (which must stay `>= 80%`) and inflate cyclomatic complexity.
3. **Surgical Scope Discipline:** Touch only what the current task requires. Remove imports, variables, or functions that your changes make unused, and do not refactor unrelated code without permission.
4. **Root Cause Resolution:** Fix underlying causes rather than applying temporary workarounds or suppressing linter/type rules.
5. **Concise & Emoji-Free:** Keep docstrings, comments, and documentation concise. Add comments only where the "why" is non-obvious. Never use emojis in code, UI, or documentation.
6. **Modernity:** Use current stable APIs and package versions configured in the repository; avoid deprecated methods.

## Python Standards (`backend/`, `agent/`)

- **Package & Script Runner:** Always use `uv` (`uv run`, `uv add`, `uv sync`). Never invoke `python`, `python3`, or `pip` directly.
- **Typing & Docstrings:** Annotate all function signatures and return types so `pyright` passes cleanly. Provide a concise module docstring and a one-line docstring on every FastAPI route and agent tool.
- **FastAPI Conventions:** Every route must define an explicit `operation_id`, a one-line docstring, and no optional inputs unless required by the spec.
- **Complexity & Lint Limits (enforced by Ruff):**
  - Cyclomatic complexity (`C90`): max `10` per function.
  - Enabled rule sets: `E`, `F`, `W`, `I`, `B`, `SIM`, `UP`, `PL`, `S` (Bandit security), `PT` (pytest), `FAST` (FastAPI), and `PLR1702` (max nested blocks).

### Common `uv` Commands

| Command | Example | Action |
| :--- | :--- | :--- |
| **`uv run`** | `uv run pytest -q` | Run a command or script in the managed virtual environment |
| **`uv sync`** | `uv sync` | Sync the virtual environment with `uv.lock` |
| **`uv add`** | `uv add httpx` | Add a dependency to `pyproject.toml` and install it |
| **`uv remove`** | `uv remove requests` | Remove a dependency from the project |
| **`uv lock`** | `uv lock` | Update `uv.lock` without installing |
| **`uv tree`** | `uv tree` | Display the dependency tree |

## TypeScript & React Standards (`dashboard/`, `e2e/`)

- **Strict Typing:** TypeScript `strict` mode is enabled with `typescript-eslint` (`strictTypeChecked` and `stylisticTypeChecked`). Never use `any`, unsafe type assertions, or `@ts-ignore`.
- **Quality & Accessibility (enforced by ESLint):**
  - SonarJS (`eslint-plugin-sonarjs`), React Hooks (`eslint-plugin-react-hooks`), and JSX Accessibility (`eslint-plugin-jsx-a11y-x`) rules are enforced as errors.
  - Structural limits: max cyclomatic complexity `15`, max depth `4`, max `5` parameters, max `200` lines per function, and max `500` lines per file (excluding blanks and comments).
  - Unused eslint-disable directives fail the build (`reportUnusedDisableDirectives: "error"`).
- **Styling:** Follow `docs/BRAND.md` using vanilla CSS with custom properties. No external CSS frameworks.

## Information Retrieval & Tooling

- **Library & API Documentation:** Prefer **Context7** automatically whenever checking library/API documentation, framework patterns, or configuration steps.
- **Web Search & Scraping:** Use `tavily_search` (with `search_depth="advanced"` and `include_answer="advanced"`) for general web searches, and `tavily_extract` (with `extract_depth="advanced"`) when scraping detailed web pages.
- **Browser Automation:** Use the `playwright-cli` skill and CLI for interactive browser inspection and verification, and `@playwright/test` (`npm run e2e`) for automated end-to-end test suites.
