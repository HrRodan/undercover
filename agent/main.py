"""The UnderCover Agent."""

import os
from contextvars import ContextVar
from typing import Any

import httpx
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

load_dotenv(override=True)

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "openai/gpt-6-luna"
HTTP_CONFLICT = 409

_ACTIVE_CLAIM_ID: ContextVar[str | None] = ContextVar("_ACTIVE_CLAIM_ID", default=None)


def backend() -> httpx.Client:
    """Return a client for the UnderCover backend."""
    return httpx.Client(base_url=BACKEND_URL, timeout=30)


def _log_step(client: httpx.Client, message: str, claim_id: str | None = None) -> None:
    """Record a progress step on the active claim if a claim ID is known."""
    target_claim_id = claim_id or _ACTIVE_CLAIM_ID.get()
    if target_claim_id is None:
        return
    response = client.post(
        f"/api/claims/{target_claim_id}/steps",
        json={"message": message},
    )
    response.raise_for_status()


@tool
def check_backend() -> str:
    """Check whether the UnderCover backend is running."""
    with backend() as client:
        response = client.get("/api/health")
    response.raise_for_status()
    return str(response.json()["status"])


@tool
def get_claim(claim_id: str) -> dict[str, Any]:
    """Fetch the full claim record including story, items, and documents."""
    _ACTIVE_CLAIM_ID.set(claim_id)
    with backend() as client:
        _log_step(client, f"Reading claim {claim_id}", claim_id)
        response = client.get(f"/api/claims/{claim_id}")
    response.raise_for_status()
    data: dict[str, Any] = response.json()
    return data


@tool
def get_policy(policy_id: str) -> dict[str, Any]:
    """Fetch the policy record along with plan limits and add-on details."""
    with backend() as client:
        _log_step(client, f"Checking policy {policy_id} and plan limits")
        response = client.get(f"/api/policies/{policy_id}")
    response.raise_for_status()
    data: dict[str, Any] = response.json()
    return data


@tool
def get_customer(customer_id: str) -> dict[str, Any]:
    """Fetch the customer profile and prior claim history."""
    with backend() as client:
        _log_step(client, f"Reviewing customer claim history for {customer_id}")
        response = client.get(f"/api/customers/{customer_id}")
    response.raise_for_status()
    data: dict[str, Any] = response.json()
    return data


@tool
def get_policy_wording() -> dict[str, Any]:
    """Fetch the contractual policy wording document."""
    with backend() as client:
        _log_step(client, "Reading policy wording")
        response = client.get("/api/policy-wording")
    response.raise_for_status()
    data: dict[str, Any] = response.json()
    return data


@tool
def decide_claim(
    claim_id: str,
    decision: str,
    payout: float,
    policy_section: str,
    reason: str,
) -> dict[str, Any]:
    """Record the decision, payout amount, policy section, and explanation."""
    _ACTIVE_CLAIM_ID.set(claim_id)
    with backend() as client:
        _log_step(
            client,
            f"Recording decision: {decision} (${payout:,.2f})",
            claim_id,
        )
        response = client.post(
            f"/api/claims/{claim_id}/decision",
            json={
                "decision": decision,
                "payout": payout,
                "policy_section": policy_section,
                "reason": reason,
            },
        )
    response.raise_for_status()
    data: dict[str, Any] = response.json()
    return data


@tool
def pay_claim(claim_id: str, amount: float) -> dict[str, Any]:
    """Request payment of an approved payout amount for a claim."""
    _ACTIVE_CLAIM_ID.set(claim_id)
    with backend() as client:
        _log_step(client, f"Requesting payout of ${amount:,.2f}", claim_id)
        response = client.post(
            f"/api/claims/{claim_id}/pay",
            json={"amount": amount},
        )
        if response.status_code == HTTP_CONFLICT:
            _log_step(
                client,
                f"Payment of ${amount:,.2f} held pending handler sign-off",
                claim_id,
            )
            return {
                "status": "pending_sign_off",
                "detail": str(response.json().get("detail", "")),
            }
    response.raise_for_status()
    data: dict[str, Any] = response.json()
    return data


AGENT_TOOLS = [
    check_backend,
    get_claim,
    get_policy,
    get_customer,
    get_policy_wording,
    decide_claim,
    pay_claim,
]


def fetch_instructions() -> str:
    """Fetch the read-only system prompt from the backend."""
    with backend() as client:
        response = client.get("/api/instructions")
    response.raise_for_status()
    return str(response.json()["instructions"])


def model() -> ChatOpenAI:
    """Return the model named in MODEL_NAME, or GPT-6 Luna by default."""
    name = os.getenv("MODEL_NAME")
    return ChatOpenAI(
        model=name or DEFAULT_MODEL,
        base_url=OPENROUTER_BASE_URL,
        api_key=SecretStr(os.environ["OPENROUTER_API_KEY"]),
        reasoning_effort=None if name else "low",
    )


def run(claim_id: str, thread_id: str, llm: BaseChatModel | None = None) -> str:
    """Run the agent on one claim and return its final reply."""
    _ACTIVE_CLAIM_ID.set(claim_id)
    instructions = fetch_instructions()
    agent = create_agent(
        llm or model(),
        tools=AGENT_TOOLS,
        system_prompt=instructions,
    )
    result = agent.invoke(
        {"messages": [{"role": "user", "content": f"Claim {claim_id}"}]},
        config={"configurable": {"thread_id": thread_id}},
    )
    return str(result["messages"][-1].text)
