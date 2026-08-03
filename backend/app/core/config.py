from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)

    app_name: str = "BreachSim"
    environment: str = "development"
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 60 * 8
    database_url: str = "sqlite:///./breachsim.db"
    redis_url: str = "redis://redis:6379/0"
    encryption_key: str = "3zcD2n9il4f-aM1MAt7R9Hkg4g7H4FrJDE0ctCcf18Y="
    frontend_base_url: str = "http://localhost:3000"
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://localhost:3001",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:3001",
        ]
    )
    demo_org_name: str = "Northwind Financial Labs"
    demo_org_slug: str = "northwind-financial-labs"
    seed_demo_content: bool = False
    lab_email_provider_enabled: bool = False
    lab_sms_provider_enabled: bool = False
    llm_provider: str = "ollama"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "llama2-uncensored:latest"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1-mini"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    training_domain_placeholder: str = "training.breachsim.local"
    report_export_dir: str = "sample_outputs"

    # --- Synthetic media (real voice/video cloning) ---
    # Providers are pluggable. With none configured, the simulators fall back to the
    # in-browser speech engine, so the platform still runs with zero paid services.
    media_storage_dir: str = "media_store"
    #: Default retention for a generated clip; a persona's consent expiry always wins if sooner.
    media_retention_days: int = 30
    #: Hard ceiling on an uploaded consent sample, in megabytes.
    media_max_upload_mb: int = 25

    voice_clone_provider: str = "none"  # none | elevenlabs
    elevenlabs_api_key: str | None = None
    elevenlabs_base_url: str = "https://api.elevenlabs.io"
    elevenlabs_model_id: str = "eleven_multilingual_v2"
    #: Voice cloning that mimics an identifiable person is gated behind this flag in
    #: addition to per-persona consent. Instant Voice Cloning requires a paid plan.
    elevenlabs_allow_voice_cloning: bool = True

    video_clone_provider: str = "none"  # none | did
    did_api_key: str | None = None
    did_base_url: str = "https://api.d-id.com"


#: Shipped placeholder. Signing tokens with a publicly-known secret means anyone can
#: forge an admin token, which defeats every RBAC check in the product.
INSECURE_SECRET_PLACEHOLDER = "change-me-in-production"


@lru_cache
def get_settings() -> Settings:
    resolved = Settings()
    if resolved.environment.lower() in {"production", "prod"} and (
        resolved.secret_key == INSECURE_SECRET_PLACEHOLDER or len(resolved.secret_key) < 32
    ):
        raise RuntimeError(
            "SECRET_KEY is unset, still the shipped placeholder, or shorter than 32 characters. "
            "Set a strong unique SECRET_KEY before running in production — tokens signed with "
            "the default secret can be forged by anyone."
        )
    return resolved


settings = get_settings()


def secret_key_is_insecure() -> bool:
    """True when the JWT secret would not be safe outside local development."""
    return settings.secret_key == INSECURE_SECRET_PLACEHOLDER or len(settings.secret_key) < 32
