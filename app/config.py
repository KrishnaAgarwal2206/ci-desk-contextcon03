"""Settings loaded from the backend environment (.env). Secrets never leave the server."""
import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def _b(name: str, default: str) -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "on")


@dataclass
class Settings:
    crustdata_api_key: str = field(default_factory=lambda: os.getenv("CRUSTDATA_API_KEY", "").strip())
    crustdata_base_url: str = "https://api.crustdata.com"
    crustdata_api_version: str = "2025-11-01"
    run_credit_cap: float = field(default_factory=lambda: float(os.getenv("CRUSTDATA_RUN_CREDIT_CAP", "150")))
    crustdata_timeout_s: float = 25.0

    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", "").strip())
    anthropic_model: str = field(default_factory=lambda: os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5"))
    anthropic_api_version: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_VERSION", "2023-06-01"))
    anthropic_url: str = "https://api.anthropic.com/v1/messages"
    llm_enabled: bool = field(default_factory=lambda: _b("LLM_ENABLED", "true"))
    llm_spend_cap_usd: float = field(default_factory=lambda: float(os.getenv("LLM_SPEND_CAP_USD", "5")))
    llm_max_calls_per_request: int = field(default_factory=lambda: int(os.getenv("LLM_MAX_CALLS_PER_REQUEST", "3")))
    llm_max_output_tokens: int = field(default_factory=lambda: int(os.getenv("LLM_MAX_OUTPUT_TOKENS", "1200")))
    # Rich multi-stakeholder brief synthesis needs more room than planning/feedback calls.
    llm_synth_max_output_tokens: int = field(default_factory=lambda: int(os.getenv("LLM_SYNTH_MAX_OUTPUT_TOKENS", "4000")))
    price_in_per_mtok: float = field(default_factory=lambda: float(os.getenv("ANTHROPIC_PRICE_INPUT_PER_MTOK", "2")))
    price_out_per_mtok: float = field(default_factory=lambda: float(os.getenv("ANTHROPIC_PRICE_OUTPUT_PER_MTOK", "10")))

    database_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///./contextcon03.db"))

    watch_auto_create: bool = field(default_factory=lambda: _b("WATCH_AUTO_CREATE", "true"))
    public_webhook_url: str = field(default_factory=lambda: os.getenv("PUBLIC_WEBHOOK_URL", "").strip())
    watch_every_hours: int = field(default_factory=lambda: max(24, int(os.getenv("WATCH_EVERY_HOURS", "168"))))
    watch_max_results_per_run: int = field(default_factory=lambda: min(25, int(os.getenv("WATCH_MAX_RESULTS_PER_RUN", "25"))))
    watch_max_entities: int = field(default_factory=lambda: min(10, int(os.getenv("WATCH_MAX_ENTITIES", "10"))))
    webhook_tolerance_s: int = 300

    # Per-run research caps (CREDIT_BUDGET.md)
    max_companies: int = 6
    max_jobs_per_company: int = 10
    max_people_per_company: int = 5
    max_web_results_per_company: int = 3


settings = Settings()
