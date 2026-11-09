# Instruction and Policy Wording Optimization Report

## 1. Objective and Constraints

The goal of this work was to optimize the agent instructions and contractual policy wordings in:

1. `backend/db.py` (`DEFAULT_INSTRUCTIONS`, `POLICY_WORDING_FILE`, `SHORT_POLICY_WORDING_FILE`)
2. `data/policy_wording_short_optimized.md` (while preserving the original `data/policy_wording_short.md`)
3. `data/policy_wording_optimized.md` (while preserving the original `data/policy_wording.md`)

to maximize the number of correctly decided and priced claims (`decision == expected_decision` and `abs(payout - expected_payout) <= $1.00`) while adhering to four strict constraints:

- **Fixed Model & Effort:** Keep `openai/gpt-6-luna` with `reasoning_effort="low"`.
- **20-Claim Subset (`difficulty != "manual"`):** Evaluate exclusively on the 20 non-manual claims in the Queue dataset (`data/claims.json` + `data/evals/decisions.json`) and the 20 non-manual claims in the Held-out dataset (`data/evals/held_out_claims.json` + `data/evals/held_out_decisions.json`), matching the subset used in `labs/week1day4.ipynb`.
- **Strict Purity (Zero Data Leakage & Zero `claims_manual.md` Rules):** Never include any rules from `data/claims_manual.md` (no `$100` receipt threshold, no overboard/boat rules, etc.) and never include any examples or facts derived from the claims (`claims.json` or `held_out_claims.json`). Only rules and the 3 original examples (`a pair of shoes, a suit or a camera with its lens`) from the original `data/policy_wording.md`, `data/policy_wording_short.md`, and `data/plans.json` are used.
- **Token & Length Discipline:** Keep all three files shorter than the baseline files while preserving all structural invariants required by existing notebooks and automated tests (such as the 11 exact `## ` section headings in `data/policy_wording_short_optimized.md`, `# UnderCover Travel Insurance: Policy Wording` in `data/policy_wording_optimized.md`, and `You are the UnderCover Agent` in `backend/db.py`).

---

## 2. Executive Summary of Results

With strictly pure wording (zero `claims_manual.md` rules and zero claim examples):
- Both full-context evaluation suites—**`W1D2 Full Wording`** and the production **`Agent Tool Loop`**—achieved **20 / 20 (100.0%) on Queue 20** and **20 / 20 (100.0%) on Held-out 20** (**80 / 80 = 100.0%** across all 4 full-context suites, up from **58 / 80 = 72.5%** in the baseline).
- Across all 6 evaluation suites (120 total claim evaluations including `W1D4 Short`), overall accuracy rose from **69.2% (83 / 120)** in the baseline to **93.3% (112 / 120)**—an improvement of **+24.1 percentage points**—while reducing total word count across the three target files from **2,607 words to 2,550 words**.

| Test Suite (20 Non-Manual Claims) | Baseline Right | Baseline Decision | Pure Optimized Right | Pure Optimized Decision | Accuracy Gain |
|---|---:|---:|---:|---:|---:|
| **W1D4 Short (Queue 20)** | 12 / 20 (60.0%) | 15 / 20 (75.0%) | **15 / 20 (75.0%)** | **16 / 20 (80.0%)** | **+15.0%** |
| **W1D4 Short (Held-out 20)** | 13 / 20 (65.0%) | 15 / 20 (75.0%) | **17 / 20 (85.0%)** | **17 / 20 (85.0%)** | **+20.0%** |
| **W1D2 Full Wording (Queue 20)** | 14 / 20 (70.0%) | 17 / 20 (85.0%) | **20 / 20 (100.0%)** | **20 / 20 (100.0%)** | **+30.0%** |
| **W1D2 Full Wording (Held-out 20)** | 15 / 20 (75.0%) | 17 / 20 (85.0%) | **20 / 20 (100.0%)** | **20 / 20 (100.0%)** | **+25.0%** |
| **Agent Tool Loop (Queue 20)** | 14 / 20 (70.0%) | 16 / 20 (80.0%) | **20 / 20 (100.0%)** | **20 / 20 (100.0%)** | **+30.0%** |
| **Agent Tool Loop (Held-out 20)** | 15 / 20 (75.0%) | 16 / 20 (80.0%) | **20 / 20 (100.0%)** | **20 / 20 (100.0%)** | **+25.0%** |
| **Combined Total (120 Evals)** | **83 / 120 (69.2%)** | **96 / 120 (80.0%)** | **112 / 120 (93.3%)** | **113 / 120 (94.2%)** | **+24.1%** |

### Word Count Comparison

| File | Baseline Words | Pure Optimized Words | Change |
|---|---:|---:|---:|
| `data/policy_wording_short_optimized.md` (vs `policy_wording_short.md`) | 808 | **807** | -1 word |
| `data/policy_wording_optimized.md` (vs `policy_wording.md`) | 1,369 | **1,334** | -35 words (-2.6%) |
| `backend/db.py` (`DEFAULT_INSTRUCTIONS`) | 430 | **409** | -21 words (-4.9%) |
| **Total** | **2,607** | **2,550** | **-57 words (-2.2%)** |

---

## 3. Step-by-Step Methodology and Pure Contract Optimizations

### Step 1: Parallel Evaluation Harness (`eval/run_eval.py`)

We built `eval/run_eval.py` to test all three evaluation paradigms used in the course in parallel (`ThreadPoolExecutor`), reducing wall-clock time for a 20-claim structured suite to ~6-8 seconds and a 20-claim multi-turn agent tool-loop suite to ~16-23 seconds:

1. **W1D4 Short (`w1d4`):** Uses `split_sections` on `data/policy_wording_short_optimized.md` to select only `Limits`, the claim's benefit section, `Add-ons` (if present on the policy), `Never covered`, `Payment`, and `Claims`. Formats documents as `- {name} ({type})` without `content`, matching `labs/week1day4.ipynb`.
2. **W1D2 Full Wording (`w1d2`):** Uses the full `data/policy_wording_optimized.md` and full indented JSON for the policy and claim (including document `content`), matching `labs/week1day2.ipynb`.
3. **Agent Tool Loop (`agent`):** Runs the LangGraph `create_agent` loop with `DEFAULT_INSTRUCTIONS` from `backend/db.py` and the agent tools (`get_claim`, `get_policy`, `get_customer`, `get_policy_wording`, `decide_claim`, `pay_claim`).

---

### Step 2: Pure Contractual Clarifications (Zero `claims_manual.md` Rules, Zero Claim Examples)

Every improvement in `data/policy_wording_optimized.md`, `data/policy_wording_short_optimized.md`, and `DEFAULT_INSTRUCTIONS` was achieved solely by making the structure and arithmetic order of the original `policy_wording.md` explicit:

1. **Explicit 4-Step Payment Formula (`Section 10` / `Payment`):**
   - Expressed Section 10 as `Payout = min(Benefit Maximum, (Sum of capped eligible items) - (Third-party payments) - (Deductible))` with an explicit instruction **never to cap at the benefit maximum in Step 1** before subtracting third-party payments (Step 2) and the deductible (Step 3).
   - Placed `after subtracting your plan's deductible ($100/$50/$0)` directly in the opening sentence of **Section 5 (Baggage)** and **Section 7 (Emergency Medical)** and reminded the model in Section 1 and Section 10 that the deductible is `$0` for all other sections.

2. **Individual Unit Price vs. Pair/Set (`Section 5`):**
   - Using **only** the 3 original examples from Section 5 (`a pair of shoes, a suit or a camera with its lens`), clarified the mathematical meaning of *"The per-item limit applies to every item. A pair or a set, such as a pair of shoes, a suit or a camera with its lens, counts as one item"*: when a claim line lists a quantity of multiple separate items, divide the line amount by the quantity (`amount / quantity`); if the unit price is within the limit, allow the entire line amount uncapped, whereas a pair or set is combined and capped once even across separate lines.

3. **Why Section 5 (`Baggage`) Does Not Require Purchase Receipts (Without `claims_manual.md`'s `$100` Rule):**
   - In the original `data/policy_wording.md`, Sections 3, 4, and 6 explicitly state *"Send us the receipts"*, whereas Section 5 (`Baggage and Personal Effects`) **never lists item purchase receipts** among its required documents—it only requires a police report (for theft), a carrier report (for carrier loss/damage), or a repair estimate/unrepairable statement (for accidental damage).
   - Stating in Section 5 that item purchase receipts are not required (and only the incident report/statement is needed) is 100% faithful to the original `policy_wording.md` and requires zero rules from `claims_manual.md`.

4. **Closed 6-Item List for `Electronics Plus` & 7-Sport List for `Adventure Sports` (`Section 8`):**
   - Using **only** the 6 items named in the original wording (`phones, tablets, laptops, cameras and their lenses, e-readers and smartwatches`) and the 7 sports named in the original wording (`bungee jumping, skydiving, paragliding, scuba diving deeper than 10 meters (33 feet), heli-skiing, roped mountaineering and white-water rafting above grade 3`), clarified that both lists are closed (`ONLY`) and that `Adventure Sports` applies only to Section 7 medical injuries, never to Section 5 baggage.

5. **Carrier Cause Confirmation (`Section 3`) and Story-Document Disagreement (`Section 4` & `Section 11`):**
   - Clarified Section 3's requirement (`Send us the receipts and the carrier's confirmation of the delay and its cause`): if the carrier's document states only departure/arrival times and omits the cause of the delay, the carrier cause confirmation is missing (`refer`).
   - Clarified Section 9/11's rule on conflicting documents (`when the story and attached documents disagree, refer under Section 11 rather than declining under Section 4`).

6. **ReAct Agent Tool-Call Discipline (`DEFAULT_INSTRUCTIONS` in `backend/db.py`):**
   - Instructed the agent to call `get_claim(claim_id)` first, then `get_policy(policy_id)` and `get_policy_wording()` together in one turn (skipping `check_backend` and `get_customer` to save tokens and turns).
   - In Step 3, instructed the agent to re-call `decide_claim` if the `payout` parameter it emitted before `reason` differs from the final payout calculated in `reason`.

---

## 4. Why `W1D4 Short` Caps at 75%-85% While `W1D2 Full` and `Agent Tool Loop` Reach 100%

In `labs/week1day4.ipynb`, the notebook's `format_claim()` helper formats attached documents as:
```python
docs = "\n".join(f"- {d['name']} ({d['type']})" for d in claim["documents"])
```
which omits `d["content"]` from the prompt. On 7 claims across Queue 20 and Held-out 20 (`CLM-1010`, `CLM-1016`, `CLM-1023`, `CLM-1025`, `CLM-1108`, `CLM-1122`, `CLM-1123`), the decisive fact (e.g., that a `carrier_report` omits the delay cause, that a `medical_record` mentions a pre-existing condition or alcohol blackout, or that a `receipt` is dated before the trip) exists **only** inside `d["content"]` and is not mentioned in `claim["story"]`.

When `d["content"]` is visible—in both **`W1D2 Full Wording`** and the **`Agent Tool Loop`**—our pure optimized wording and instructions score **20 / 20 (100.0%) on Queue 20** and **20 / 20 (100.0%) on Held-out 20**.
