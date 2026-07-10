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
    frontend_base_url: str = "http://127.0.0.1:3001"
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


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
