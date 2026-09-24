"""Application configuration.

All settings are read from environment variables (see backend/.env.example).
Secrets are never committed to the repository.
"""
from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "FINZ AI-Native Financial Review"
    app_version: str = "1.0.0"
    api_prefix: str = "/api"

    # --- Database -------------------------------------------------------
    # PostgreSQL connection string. Example:
    #   postgresql+psycopg://finz:finz@localhost:5432/finz
    database_url: str = "postgresql+psycopg://finz:finz@localhost:5432/finz"

    # --- LLM / Groq ------------------------------------------------------
    groq_api_key: str | None = None
    groq_model: str = "openai/gpt-oss-120b"
    # Base URL for the Groq SDK. The SDK constructs resource paths itself,
    # e.g. it appends "/openai/v1/chat/completions", so this must be the API
    # host root ("https://api.groq.com"), NOT "https://api.groq.com/openai/v1".
    # The validator below also strips any trailing "/openai/v1" segments so a
    # misconfigured env value can never double the path segment.
    groq_base_url: str = "https://api.groq.com"
    groq_timeout_seconds: float = 60.0
    groq_max_tool_iterations: int = 8

    # --- Classification ----------------------------------------------------
    enable_llm_classification: bool = True
    llm_classification_threshold: float = 0.80
    review_confidence_threshold: float = 0.92
    default_rule_confidence: float = 0.96

    # --- Review queue triggers -----------------------------------------------
    # A classification whose confidence is below review_confidence_threshold is
    # surfaced for review (LOW_CONFIDENCE). The following thresholds govern the
    # additional deterministic triggers:
    #   * unusual_amount_min_count          minimum transactions in a category
    #                                        required before outlier detection
    #   * unusual_amount_multiplier         robust (median + z * 1.4826 * MAD)
    #                                        outlier multiplier, configurable
    #   * unusual_amount_min_abs_cents      floor below which an amount is never
    #                                        considered unusual, even for small cats
    #   * review_significance_min_cents     single amounts at/above this level are
    #                                        surfaced as financially significant
    unusual_amount_min_count: int = 4
    unusual_amount_multiplier: float = 3.0
    unusual_amount_min_abs_cents: int = 50_000  # $500.00
    review_significance_min_cents: int = 2_500_000  # $25,000.00

    # --- Materiality --------------------------------------------------------
    variance_materiality_percent: float = 10.0
    variance_materiality_abs_cents: int = 50_000  # $500.00

    # --- CORS ------------------------------------------------------------------
    # Comma separated list of allowed origins, e.g. "http://localhost:5173"
    cors_origins: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    # --- Data / Seeding --------------------------------------------------------
    # Optional path to an xlsx dataset that is auto-ingested on startup when the
    # transactions table is empty (used to make a fresh deployment demo-ready).
    seed_dataset_path: str | None = None

    # --- Misc --------------------------------------------------------------------
    log_level: str = "INFO"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, v: str) -> List[str]:
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @field_validator("groq_base_url", mode="after")
    @classmethod
    def _normalize_groq_base_url(cls, v: str) -> str:
        value = (v or "").strip().rstrip("/")
        # The Groq SDK appends "/openai/v1/<resource>" to base_url. Strip any
        # number of trailing "/openai/v1" segments so only the host root stays.
        while value.endswith("/openai/v1"):
            value = value[: -len("/openai/v1")]
        return value or "https://api.groq.com"

    @property
    def cors_origin_list(self) -> List[str]:
        return self.cors_origins

    @property
    def review_threshold(self) -> float:
        return self.review_confidence_threshold

    @property
    def llm_threshold(self) -> float:
        return self.llm_classification_threshold


@lru_cache
def get_settings() -> Settings:
    return Settings()