"""Centralized configuration for the UnderCover Agent and subagent harness."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv(override=True)

DEFAULT_BACKEND_URL = "http://localhost:8000"
DEFAULT_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "openai/gpt-6-luna"
DEFAULT_QUEUE_REASONING_EFFORT = "medium"
DEFAULT_CLAIM_REASONING_EFFORT = "low"
DEFAULT_MODEL_TIMEOUT_SECONDS = 120
DEFAULT_MODEL_MAX_RETRIES = 3
DEFAULT_RECURSION_LIMIT = 200


@dataclass(frozen=True)
class AgentConfig:
    """Resolved model, reasoning effort, and harness execution settings."""

    backend_url: str
    openrouter_base_url: str
    default_model: str
    queue_model_name: str
    claim_model_name: str
    queue_reasoning_effort: str | None
    claim_reasoning_effort: str | None
    model_timeout_seconds: int
    model_max_retries: int
    recursion_limit: int


def _resolve_reasoning(
    env_var: str, default_effort: str, explicit_model_override: str | None
) -> str | None:
    """Resolve reasoning effort, allowing none when a custom model overrides."""
    raw = os.getenv(env_var)
    if raw is not None:
        cleaned = raw.strip().lower()
        return None if cleaned in ("", "none") else cleaned
    if explicit_model_override:
        return None
    return default_effort


def get_agent_config() -> AgentConfig:
    """Load agent configuration from environment variables with defaults."""
    model_override = os.getenv("MODEL_NAME")
    base_model = model_override or DEFAULT_MODEL
    queue_override = os.getenv("QUEUE_MODEL_NAME")
    claim_override = os.getenv("CLAIM_MODEL_NAME")
    queue_model = queue_override or base_model
    claim_model = claim_override or base_model

    return AgentConfig(
        backend_url=os.getenv("BACKEND_URL", DEFAULT_BACKEND_URL),
        openrouter_base_url=os.getenv(
            "OPENROUTER_BASE_URL", DEFAULT_OPENROUTER_BASE_URL
        ),
        default_model=base_model,
        queue_model_name=queue_model,
        claim_model_name=claim_model,
        queue_reasoning_effort=_resolve_reasoning(
            "QUEUE_REASONING_EFFORT",
            DEFAULT_QUEUE_REASONING_EFFORT,
            queue_override or model_override,
        ),
        claim_reasoning_effort=_resolve_reasoning(
            "CLAIM_REASONING_EFFORT",
            DEFAULT_CLAIM_REASONING_EFFORT,
            claim_override or model_override,
        ),
        model_timeout_seconds=int(
            os.getenv("MODEL_TIMEOUT_SECONDS", str(DEFAULT_MODEL_TIMEOUT_SECONDS))
        ),
        model_max_retries=int(
            os.getenv("MODEL_MAX_RETRIES", str(DEFAULT_MODEL_MAX_RETRIES))
        ),
        recursion_limit=int(
            os.getenv("AGENT_RECURSION_LIMIT", str(DEFAULT_RECURSION_LIMIT))
        ),
    )
