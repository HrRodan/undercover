"""Parallel evaluation suite for UnderCover instructions and policy wording."""

import json
import os
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from openai import OpenAI
from pydantic import BaseModel, Field, SecretStr

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.db import (  # noqa: E402
    DEFAULT_INSTRUCTIONS,
    FULL_POLICY_WORDING_FILE,
    POLICY_WORDING_FILE,
    SHORT_POLICY_WORDING_FILE,
)

DATA = ROOT / "data"
RESULTS_DIR = Path(__file__).resolve().parent / "results"
APPROVAL_LIMIT = 1000.0
MIN_TAG_ARGS = 3
MAX_WORKERS = 12
load_dotenv(ROOT / ".env", override=True)

openrouter = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
    timeout=120,
    max_retries=5,
)


class ClaimDecision(BaseModel):
    """A claims handler's decision on one claim."""

    rationale: str = Field(
        description=(
            "2-3 sentences to explain the decision along with the relevant "
            "section of the policy"
        )
    )
    decision: Literal["approve", "decline", "refer"]
    payout: float = Field(
        description=(
            "The amount to pay in US dollars, or 0 for a decline or a referral"
        )
    )


BENEFITS: dict[str, str] = {
    "trip_cancellation": "Cancellation and Interruption",
    "trip_interruption": "Cancellation and Interruption",
    "trip_delay": "Trip Delay",
    "baggage_delay": "Baggage Delay",
    "baggage": "Baggage",
    "passport": "Passport",
    "emergency_medical": "Emergency Medical",
}

W1D4_INSTRUCTIONS = "\n".join(
    [
        "You are a claims handler at UnderCover Travel Insurance.",
        "Decide the claim you are given, using the policy wording below and the "
        "customer's policy record.",
        "",
        "Choose one decision:",
        "- approve: the wording covers the claim and the required documents are "
        "attached. Work out the payout using the Payment section.",
        "- decline: the wording does not cover the claim.",
        "- refer: a colleague needs to look at it, because a required document is "
        "missing, or the story and the documents disagree, or the wording does not "
        "settle the question.",
        "",
    ]
)

W1D2_INSTRUCTIONS = "\n".join(
    [
        "You are a claims handler at UnderCover Travel Insurance.",
        "Decide the claim you are given, using the policy wording below and the "
        "customer's policy record.",
        "",
        "Choose one decision:",
        "- approve: the wording covers the claim and the required documents are "
        "attached. Work out the payout using section 10.",
        "- decline: the wording does not cover the claim.",
        "- refer: a colleague needs to look at it, because a required document is "
        "missing, or the story and the documents disagree, or the wording does not "
        "settle the question.",
        "",
    ]
)


def load_json(rel_path: str) -> Any:
    """Read and parse a JSON file relative to the data directory."""
    return json.loads((DATA / rel_path).read_text(encoding="utf-8"))


def split_sections(wording: str) -> tuple[str, dict[str, str]]:
    """Split markdown wording by '## ' headings into opening text and sections dict."""
    parts = wording.split("\n## ")
    sections = {part.split("\n")[0].strip(): "## " + part for part in parts[1:]}
    return parts[0], sections


def make_w1d4_wording(
    claim: dict[str, Any],
    policies: dict[str, dict[str, Any]],
    short_wording: str,
) -> str:
    """Build the claim-specific wording subset used in Week 1 Day 4."""
    opening, sections = split_sections(short_wording)
    headings = ["Limits", BENEFITS[claim["claim_type"]]]
    if policies[claim["policy_id"]]["add_ons"]:
        headings.append("Add-ons")
    headings += ["Never covered", "Payment", "Claims"]
    return "\n\n".join(
        [opening.strip()] + [sections[heading].strip() for heading in headings]
    )


def make_w1d4_messages(
    claim: dict[str, Any],
    policies: dict[str, dict[str, Any]],
    short_wording: str,
) -> list[dict[str, str]]:
    """Build the compact prompt messages used in Week 1 Day 4."""
    policy = policies[claim["policy_id"]]
    record = {
        k: v
        for k, v in policy.items()
        if k not in ["policy_id", "customer_id", "sold_through", "status"]
    }
    details = {
        k: v
        for k, v in claim.items()
        if k not in ["policy_id", "customer_id", "status"]
    }
    details["documents"] = [
        {"name": doc["name"], "type": doc["type"]} for doc in claim["documents"]
    ]
    user_prompt = (
        f"# Policy record\n\n{json.dumps(record)}\n\n# Claim\n\n{json.dumps(details)}\n"
    )
    wording_subset = make_w1d4_wording(claim, policies, short_wording)
    sys_prompt = f"{W1D4_INSTRUCTIONS}\n{wording_subset}\n"
    return [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": user_prompt},
    ]


def make_w1d2_messages(
    claim: dict[str, Any],
    policies: dict[str, dict[str, Any]],
    full_wording: str,
) -> list[dict[str, str]]:
    """Build the full wording and indented JSON messages used in Week 1 Day 2."""
    policy = policies[claim["policy_id"]]
    user_prompt = (
        f"# Policy record\n\n{json.dumps(policy, indent=2)}\n\n"
        f"# Claim\n\n{json.dumps(claim, indent=2)}\n"
    )
    return [
        {"role": "system", "content": f"{W1D2_INSTRUCTIONS}\n{full_wording}\n"},
        {"role": "user", "content": user_prompt},
    ]


def evaluate_structured_one(
    claim: dict[str, Any],
    label: dict[str, Any],
    messages: list[dict[str, str]],
    model: str = "openai/gpt-6-luna",
    effort: str = "low",
) -> dict[str, Any]:
    """Evaluate a single claim via OpenRouter structured outputs."""
    start = time.time()
    response = openrouter.chat.completions.parse(
        model=model,
        messages=messages,  # type: ignore[arg-type]
        response_format=ClaimDecision,
        reasoning_effort=effort,  # type: ignore[arg-type]
        extra_body={"provider": {"require_parameters": True}},
    )
    ans = response.choices[0].message.parsed
    if ans is None:
        msg = f"Failed to parse structured output for {claim['claim_id']}"
        raise RuntimeError(msg)
    dec_right = ans.decision == label["decision"]
    right = dec_right and abs(ans.payout - float(label["payout"])) <= 1.0
    usage = response.usage
    return {
        "claim_id": claim["claim_id"],
        "difficulty": label["difficulty"],
        "failure_class": label["failure_class"],
        "decision": ans.decision,
        "expected_decision": label["decision"],
        "payout": ans.payout,
        "expected_payout": float(label["payout"]),
        "decision_right": dec_right,
        "right": right,
        "rationale": ans.rationale,
        "input_tokens": usage.prompt_tokens if usage else 0,
        "output_tokens": usage.completion_tokens if usage else 0,
        "cost": float(getattr(usage, "cost", 0.0) or 0.0),
        "seconds": round(time.time() - start, 2),
    }


def _build_agent_tools(context: dict[str, Any], recorded: dict[str, Any]) -> list[Any]:
    """Construct the in-memory backend tools for a single agent run."""
    claims_map: dict[str, dict[str, Any]] = context["claims_map"]
    policies_map: dict[str, dict[str, Any]] = context["policies_map"]
    customers_map: dict[str, dict[str, Any]] = context["customers_map"]
    plans_map: dict[str, dict[str, Any]] = context["plans_map"]
    addons_map: dict[str, dict[str, Any]] = context["addons_map"]
    deductible_applies_to: list[str] = context["deductible_applies_to"]
    full_wording: str = context["full_wording"]

    @tool
    def check_backend() -> str:
        """Check whether the UnderCover backend is running."""
        return "ok"

    @tool
    def get_claim(claim_id: str) -> dict[str, Any]:
        """Fetch the claim record including policy_id, customer_id, and story."""
        c = claims_map.get(claim_id)
        return (
            {**c, "status": "in_progress", "steps": []}
            if c
            else {"error": f"Claim {claim_id} not found"}
        )

    @tool
    def get_policy(policy_id: str) -> dict[str, Any]:
        """Fetch the policy record by policy_id (such as POL-2001) and plan limits."""
        pol = policies_map.get(policy_id)
        if not pol:
            return {"error": f"Policy {policy_id} not found."}
        plan = plans_map[pol["plan"]]
        addons = [addons_map[a] for a in pol["add_ons"] if a in addons_map]
        return {
            **pol,
            "plan_details": {**plan, "deductible_applies_to": deductible_applies_to},
            "add_on_details": addons,
        }

    @tool
    def get_customer(customer_id: str) -> dict[str, Any]:
        """Fetch the customer profile and prior claims by customer_id (CUS-3001)."""
        return customers_map.get(
            customer_id, {"error": f"Customer {customer_id} not found."}
        )

    @tool
    def get_policy_wording() -> dict[str, Any]:
        """Fetch the contractual policy wording document."""
        return {"version": "2026.1", "content": full_wording}

    @tool
    def decide_claim(
        claim_id: str,
        decision: str,
        payout: float,
        policy_section: str,
        reason: str,
    ) -> dict[str, Any]:
        """Record the decision, payout amount, policy section, and explanation."""
        aliases = {
            "approve": "approve",
            "approved": "approve",
            "decline": "decline",
            "declined": "decline",
            "refer": "refer",
            "referred": "refer",
        }
        norm = aliases.get(decision.strip().lower(), decision.strip().lower())
        final_payout = float(payout) if norm == "approve" else 0.0
        recorded.update(
            {
                "decision": norm,
                "payout": final_payout,
                "policy_section": policy_section,
                "reason": reason,
            }
        )
        return {"claim_id": claim_id, "decision": norm, "payout": final_payout}

    @tool
    def pay_claim(claim_id: str, amount: float) -> dict[str, Any]:
        """Request payment of an approved payout amount for a claim."""
        if amount > APPROVAL_LIMIT:
            return {"status": "pending_sign_off"}
        return {"claim_id": claim_id, "payment_status": "paid", "amount_paid": amount}

    return [
        check_backend,
        get_claim,
        get_policy,
        get_customer,
        get_policy_wording,
        decide_claim,
        pay_claim,
    ]


def _extract_agent_usage(messages: list[Any]) -> tuple[int, int, float]:
    """Sum input tokens, output tokens, and cost across AI messages."""
    in_tok = 0
    out_tok = 0
    cost = 0.0
    for m in messages:
        if getattr(m, "type", None) == "ai":
            tu = m.response_metadata.get("token_usage", {})
            in_tok += int(tu.get("prompt_tokens", 0) or 0)
            out_tok += int(tu.get("completion_tokens", 0) or 0)
            cost += float(tu.get("cost", 0.0) or 0.0)
    return in_tok, out_tok, cost


def evaluate_agent_one(
    claim: dict[str, Any],
    label: dict[str, Any],
    context: dict[str, Any],
    model_name: str = "openai/gpt-6-luna",
    effort: str = "low",
) -> dict[str, Any]:
    """Run the UnderCover Agent tool loop for a single claim in memory."""
    recorded: dict[str, Any] = {}
    tools = _build_agent_tools(context, recorded)
    start = time.time()
    llm = ChatOpenAI(
        model=model_name,
        base_url="https://openrouter.ai/api/v1",
        api_key=SecretStr(os.environ["OPENROUTER_API_KEY"]),
        reasoning_effort=effort,
        timeout=120,
        max_retries=5,
    )
    agent = create_agent(llm, tools=tools, system_prompt=context["instructions"])
    res = agent.invoke(
        {"messages": [{"role": "user", "content": f"Claim {claim['claim_id']}"}]}
    )
    in_tok, out_tok, cost = _extract_agent_usage(res["messages"])
    dec = str(recorded.get("decision", "none"))
    pay = float(recorded.get("payout", 0.0))
    dec_right = dec == label["decision"]
    right = dec_right and abs(pay - float(label["payout"])) <= 1.0
    return {
        "claim_id": claim["claim_id"],
        "difficulty": label["difficulty"],
        "failure_class": label["failure_class"],
        "decision": dec,
        "expected_decision": label["decision"],
        "payout": pay,
        "expected_payout": float(label["payout"]),
        "decision_right": dec_right,
        "right": right,
        "rationale": str(recorded.get("reason", "")),
        "input_tokens": in_tok,
        "output_tokens": out_tok,
        "cost": cost,
        "seconds": round(time.time() - start, 2),
    }


def summarize_results(
    name: str, results: list[dict[str, Any]], wall_s: float
) -> dict[str, Any]:
    """Aggregate and print metrics for a completed evaluation suite."""
    results.sort(key=lambda r: str(r["claim_id"]))
    dec_right = sum(1 for r in results if r["decision_right"])
    both_right = sum(1 for r in results if r["right"])
    avg_in_tok = round(sum(int(r["input_tokens"]) for r in results) / len(results))
    avg_out_tok = round(sum(int(r["output_tokens"]) for r in results) / len(results))
    total_cost = sum(float(r["cost"]) for r in results)
    misses = [r for r in results if not r["right"]]
    print(
        f"[{name}] {both_right}/{len(results)} right "
        f"({100 * both_right / len(results):.1f}%), "
        f"decision: {dec_right}/{len(results)} "
        f"({100 * dec_right / len(results):.1f}%), "
        f"avg_in_tok: {avg_in_tok}, avg_out_tok: {avg_out_tok}, "
        f"cost: ${total_cost:.4f}, wall: {wall_s}s"
    )
    for m in misses:
        print(
            f"  MISS {m['claim_id']} ({m['difficulty']}/{m['failure_class']}): "
            f"got {m['decision']} ${m['payout']} vs expected "
            f"{m['expected_decision']} ${m['expected_payout']} | {m['rationale']}"
        )
    return {
        "name": name,
        "total": len(results),
        "decision_right": dec_right,
        "right": both_right,
        "avg_in_tok": avg_in_tok,
        "avg_out_tok": avg_out_tok,
        "cost": total_cost,
        "wall_s": wall_s,
        "results": results,
        "misses": misses,
    }


def run_structured_suite(
    name: str,
    claims: list[dict[str, Any]],
    labels: dict[str, dict[str, Any]],
    msg_builder: Any,
    model: str = "openai/gpt-6-luna",
) -> dict[str, Any]:
    """Run a parallel structured-output evaluation suite."""
    t0 = time.time()
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futs = {
            pool.submit(
                evaluate_structured_one,
                c,
                labels[c["claim_id"]],
                msg_builder(c),
                model,
            ): c["claim_id"]
            for c in claims
        }
        for fut in as_completed(futs):
            results.append(fut.result())
    return summarize_results(name, results, round(time.time() - t0, 1))


def run_agent_suite(
    name: str,
    claims: list[dict[str, Any]],
    labels: dict[str, dict[str, Any]],
    context: dict[str, Any],
    model: str = "openai/gpt-6-luna",
) -> dict[str, Any]:
    """Run a parallel LangChain agent tool-loop evaluation suite."""
    t0 = time.time()
    suite_context = {
        **context,
        "claims_map": {c["claim_id"]: c for c in claims},
    }
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futs = {
            pool.submit(
                evaluate_agent_one,
                c,
                labels[c["claim_id"]],
                suite_context,
                model,
            ): c["claim_id"]
            for c in claims
        }
        for fut in as_completed(futs):
            results.append(fut.result())
    return summarize_results(name, results, round(time.time() - t0, 1))


def main() -> None:
    """Execute requested evaluation suites and save results."""
    policies = {p["policy_id"]: p for p in load_json("policies.json")}
    customers = {c["customer_id"]: c for c in load_json("customers.json")}
    plans_data = load_json("plans.json")
    short_wording = (DATA / SHORT_POLICY_WORDING_FILE).read_text(encoding="utf-8")
    full_wording = (DATA / FULL_POLICY_WORDING_FILE).read_text(encoding="utf-8")
    agent_wording = (DATA / POLICY_WORDING_FILE).read_text(encoding="utf-8")

    q_claims = load_json("claims.json")
    q_labels = {d["claim_id"]: d for d in load_json("evals/decisions.json")}
    q_20 = [c for c in q_claims if q_labels[c["claim_id"]]["difficulty"] != "manual"]

    h_claims = load_json("evals/held_out_claims.json")
    h_labels = {d["claim_id"]: d for d in load_json("evals/held_out_decisions.json")}
    h_20 = [c for c in h_claims if h_labels[c["claim_id"]]["difficulty"] != "manual"]

    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    tag = sys.argv[2] if len(sys.argv) >= MIN_TAG_ARGS else "latest"

    word_counts = {
        "short_wording_words": len(short_wording.split()),
        "full_wording_words": len(full_wording.split()),
        "default_instructions_words": len(DEFAULT_INSTRUCTIONS.split()),
    }
    print(
        f"Word counts: short_wording={word_counts['short_wording_words']}w, "
        f"full_wording={word_counts['full_wording_words']}w, "
        f"DEFAULT_INSTRUCTIONS={word_counts['default_instructions_words']}w"
    )

    agent_ctx = {
        "policies_map": policies,
        "customers_map": customers,
        "plans_map": {p["plan"]: p for p in plans_data["plans"]},
        "addons_map": {a["add_on"]: a for a in plans_data["add_ons"]},
        "deductible_applies_to": plans_data["deductible_applies_to"],
        "full_wording": agent_wording,
        "instructions": DEFAULT_INSTRUCTIONS,
    }

    suites: list[dict[str, Any]] = []
    if mode in ("all", "w1d4"):
        suites.append(
            run_structured_suite(
                "W1D4 Short (Queue 20)",
                q_20,
                q_labels,
                lambda c: make_w1d4_messages(c, policies, short_wording),
            )
        )
        suites.append(
            run_structured_suite(
                "W1D4 Short (Held-out 20)",
                h_20,
                h_labels,
                lambda c: make_w1d4_messages(c, policies, short_wording),
            )
        )
    if mode in ("all", "w1d2"):
        suites.append(
            run_structured_suite(
                "W1D2 Full Wording (Queue 20)",
                q_20,
                q_labels,
                lambda c: make_w1d2_messages(c, policies, full_wording),
            )
        )
        suites.append(
            run_structured_suite(
                "W1D2 Full Wording (Held-out 20)",
                h_20,
                h_labels,
                lambda c: make_w1d2_messages(c, policies, full_wording),
            )
        )
    if mode in ("all", "agent"):
        suites.append(
            run_agent_suite(
                "Agent Tool Loop (Queue 20)",
                q_20,
                q_labels,
                agent_ctx,
            )
        )
        suites.append(
            run_agent_suite(
                "Agent Tool Loop (Held-out 20)",
                h_20,
                h_labels,
                agent_ctx,
            )
        )

    payload = json.dumps(
        {
            "tag": tag,
            "mode": mode,
            "word_counts": word_counts,
            "suites": suites,
        },
        indent=2,
    )
    target_dir = (
        RESULTS_DIR
        if os.access(Path(__file__).resolve().parent, os.W_OK)
        else Path(tempfile.gettempdir()) / "undercover_eval_results"
    )
    target_dir.mkdir(parents=True, exist_ok=True)
    out_file = target_dir / f"{tag}_{mode}.json"
    out_file.write_text(payload, encoding="utf-8")
    print(f"Saved results to {out_file}")


if __name__ == "__main__":
    main()
