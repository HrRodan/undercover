"""Centralized configuration for the UnderCover backend and seed data files."""

import os
from dataclasses import dataclass
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = ROOT_DIR / "data"
DEFAULT_DB_PATH = ROOT_DIR / "undercover.db"

DEFAULT_POLICY_WORDING_FILE = "policy_wording_short_optimized.md"
DEFAULT_CLAIMS_MANUAL_FILE = "claims_manual.md"
DEFAULT_CLAIMS_FILE = "claims.json"
DEFAULT_POLICIES_FILE = "policies.json"
DEFAULT_CUSTOMERS_FILE = "customers.json"
DEFAULT_PLANS_FILE = "plans.json"
DEFAULT_HANDLERS_FILE = "handlers.json"
DEFAULT_COMPANY_FILE = "company.json"


@dataclass(frozen=True)
class BackendConfig:
    """Resolved backend file paths and runtime configuration."""

    data_dir: Path
    db_path: Path
    policy_wording_file: str
    claims_manual_file: str
    claims_file: str
    policies_file: str
    customers_file: str
    plans_file: str
    handlers_file: str
    company_file: str


def get_backend_config() -> BackendConfig:
    """Load backend configuration from environment variables with defaults."""
    data_dir = Path(os.getenv("UNDERCOVER_DATA_DIR", str(DEFAULT_DATA_DIR)))
    db_path = Path(os.getenv("UNDERCOVER_DB_PATH", str(DEFAULT_DB_PATH)))
    return BackendConfig(
        data_dir=data_dir,
        db_path=db_path,
        policy_wording_file=os.getenv(
            "UNDERCOVER_POLICY_WORDING_FILE", DEFAULT_POLICY_WORDING_FILE
        ),
        claims_manual_file=os.getenv(
            "UNDERCOVER_CLAIMS_MANUAL_FILE", DEFAULT_CLAIMS_MANUAL_FILE
        ),
        claims_file=os.getenv("UNDERCOVER_CLAIMS_FILE", DEFAULT_CLAIMS_FILE),
        policies_file=os.getenv("UNDERCOVER_POLICIES_FILE", DEFAULT_POLICIES_FILE),
        customers_file=os.getenv("UNDERCOVER_CUSTOMERS_FILE", DEFAULT_CUSTOMERS_FILE),
        plans_file=os.getenv("UNDERCOVER_PLANS_FILE", DEFAULT_PLANS_FILE),
        handlers_file=os.getenv("UNDERCOVER_HANDLERS_FILE", DEFAULT_HANDLERS_FILE),
        company_file=os.getenv("UNDERCOVER_COMPANY_FILE", DEFAULT_COMPANY_FILE),
    )
