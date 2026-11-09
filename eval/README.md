# UnderCover Evaluation Suite

This folder contains the parallel evaluation runner and full experimental documentation for optimizing UnderCover Travel Insurance's policy wordings and agent instructions:

- `backend/db.py` (`DEFAULT_INSTRUCTIONS`, `POLICY_WORDING_FILE`, `SHORT_POLICY_WORDING_FILE`)
- `data/policy_wording_short_optimized.md` (original kept in `data/policy_wording_short.md`)
- `data/policy_wording_optimized.md` (original kept in `data/policy_wording.md`)

## Files

- `run_eval.py`: Parallel evaluation script (`ThreadPoolExecutor(max_workers=20)`) that evaluates `openai/gpt-6-luna` at `low` reasoning effort on the 20 non-manual claims (`difficulty != "manual"`) across both the Queue set (`data/claims.json`) and the Held-out set (`data/evals/held_out_claims.json`).
- `RESULTS.md`: Detailed documentation of all steps, root-cause failure analyses, iterative experiments, token/word-count comparisons, and final results across all 6 test suites.
- `results/summary.json`: Structured JSON comparison of baseline vs. optimized metrics across all 6 suites.

## Test Suites

`run_eval.py` supports three evaluation modes across two 20-claim splits (6 suites / 120 claim evaluations in total):

1. `w1d4`: Replicates `labs/week1day4.ipynb` (section-routed `data/policy_wording_short.md` + compact claim JSON where document contents/summaries are omitted and only `name` and `type` are passed).
2. `w1d2`: Replicates `labs/week1day2.ipynb` (full `data/policy_wording.md` + full policy and claim JSON with document contents).
3. `agent`: Replicates the production LangGraph `create_agent` tool loop in `agent/main.py` using `DEFAULT_INSTRUCTIONS` from `backend/db.py` and `data/policy_wording.md`.

## Running the Evaluations

Run all 6 suites in parallel:

```bash
uv run python eval/run_eval.py all optimized
```

Or run an individual mode (`w1d4`, `w1d2`, or `agent`):

```bash
uv run python eval/run_eval.py w1d4 optimized
uv run python eval/run_eval.py w1d2 optimized
uv run python eval/run_eval.py agent optimized
```
