from __future__ import annotations

from functools import lru_cache
from urllib.parse import urlparse

from cryptography.fernet import Fernet
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    app_name: str = "BreachSim"
    environment: str = "development"
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 60 * 8
    session_idle_minutes: int = 30
    session_absolute_hours: int = 8
    session_cookie_name: str = "breachsim_session"
    csrf_cookie_name: str = "breachsim_csrf"
    session_cookie_secure: bool = False
    session_cookie_domain: str | None = None
    access_token_issuer: str = "breachsim"
    access_token_audience: str = "breachsim-api"
    database_url: str = "sqlite:///./breachsim.db"
    redis_url: str = "redis://redis:6379/0"
    #: Fernet key protecting integration credentials, employee phone numbers and persona
    #: summaries at rest. Deliberately has no shipped default — see ``crypto.get_fernet``.
    encryption_key: str | None = None
    frontend_base_url: str = "http://localhost:3000"
    public_url_scheme: str = "http"
    platform_training_domain: str = "localhost:3000"
    front_door_id: str | None = None
    front_door_endpoint_hostname: str | None = None
    public_dev_base_url: str = "http://localhost:8000/api/v1/public"
    max_campaign_recipients: int = 50_000
    campaign_token_ttl_days: int = 30
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://localhost:3001",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:3001",
        ]
    )
    trusted_hosts: list[str] = Field(default_factory=lambda: ["localhost", "127.0.0.1", "testserver"])
    api_docs_enabled: bool = True
    log_level: str = "INFO"
    log_json: bool = False
    login_rate_limit_count: int = 10
    login_rate_limit_window_seconds: int = 300
    public_rate_limit_count: int = 120
    public_rate_limit_window_seconds: int = 60
    demo_org_name: str = "Northwind Financial Labs"
    demo_org_slug: str = "northwind-financial-labs"
    seed_demo_content: bool = False
    bootstrap_org_name: str = "BreachSim Organization"
    bootstrap_org_slug: str = "breachsim"
    bootstrap_org_timezone: str = "UTC"
    bootstrap_admin_email: str | None = None
    bootstrap_admin_name: str = "BreachSim Administrator"
    bootstrap_admin_password: str | None = None
    bootstrap_admin_mfa_secret: str | None = None
    bootstrap_reviewer_email: str | None = None
    bootstrap_reviewer_name: str = "BreachSim Reviewer"
    bootstrap_reviewer_password: str | None = None
    bootstrap_reviewer_mfa_secret: str | None = None
    lab_email_provider_enabled: bool = False
    lab_sms_provider_enabled: bool = False
    email_delivery_backend: str = "database"  # database | rq | service_bus
    service_bus_fully_qualified_namespace: str | None = None
    service_bus_campaign_queue: str = "campaign-delivery"
    azure_key_vault_url: str | None = None
    microsoft_graph_client_id: str | None = None
    microsoft_graph_client_secret_ref: str | None = None
    microsoft_graph_redirect_uri: str | None = None
    sso_callback_url: str = "http://localhost:8000/api/v1/auth/sso/callback"
    google_service_account_secret_ref: str | None = None
    email_provider_timeout_seconds: float = 20.0
    email_provider_max_retries: int = 4
    # External narrative generation. The rule-based provider remains available as a
    # deterministic fallback and keeps the application usable without a paid service.
    ai_provider: str = "rule_based"  # rule_based | together
    together_api_key: SecretStr | None = None
    together_model: str = "openai/gpt-oss-120b"
    together_timeout_seconds: float = 45.0
    together_max_retries: int = 2
    training_domain_placeholder: str = "training.breachsim.local"
    report_export_dir: str = "sample_outputs"
    evidence_storage_account_url: str | None = None
    evidence_storage_container: str = "audit-evidence"

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


def is_production_environment(environment: str) -> bool:
    return environment.lower() in {"production", "prod"}


def validate_production_settings(resolved: Settings) -> None:
    """Fail closed when a production process is configured unsafely."""
    if not is_production_environment(resolved.environment):
        return

    errors: list[str] = []
    if resolved.secret_key == INSECURE_SECRET_PLACEHOLDER or len(resolved.secret_key) < 32:
        errors.append("SECRET_KEY must be unique and at least 32 characters")
    if not resolved.encryption_key:
        errors.append("ENCRYPTION_KEY must be explicitly configured")
    else:
        try:
            Fernet(resolved.encryption_key.encode("utf-8"))
        except (TypeError, ValueError):
            errors.append("ENCRYPTION_KEY must be a valid Fernet key")
    if resolved.database_url.startswith("sqlite"):
        errors.append("DATABASE_URL must use PostgreSQL, not SQLite")
    else:
        database = urlparse(resolved.database_url)
        if not database.hostname or not database.password:
            errors.append("DATABASE_URL must include a host and password")
    redis = urlparse(resolved.redis_url)
    if redis.scheme not in {"redis", "rediss"} or not redis.hostname or not redis.password:
        errors.append("REDIS_URL must use redis/rediss and include a host and password")
    if resolved.seed_demo_content:
        errors.append("SEED_DEMO_CONTENT must be false")
    if resolved.access_token_expire_minutes > 60:
        errors.append("ACCESS_TOKEN_EXPIRE_MINUTES must be 60 or less")
    if resolved.session_idle_minutes > 60 or resolved.session_absolute_hours > 12:
        errors.append("session limits must be at most 60 idle minutes and 12 absolute hours")
    if not resolved.session_cookie_secure:
        errors.append("SESSION_COOKIE_SECURE must be true")
    if not resolved.frontend_base_url.startswith("https://"):
        errors.append("FRONTEND_BASE_URL must use HTTPS")
    if resolved.public_url_scheme != "https":
        errors.append("PUBLIC_URL_SCHEME must be https")
    if not resolved.platform_training_domain or resolved.platform_training_domain.startswith("http"):
        errors.append("PLATFORM_TRAINING_DOMAIN must be a hostname without a scheme")
    if not resolved.front_door_id or not resolved.front_door_endpoint_hostname:
        errors.append("FRONT_DOOR_ID and FRONT_DOOR_ENDPOINT_HOSTNAME are required")
    if resolved.max_campaign_recipients > 50_000:
        errors.append("MAX_CAMPAIGN_RECIPIENTS must not exceed the certified 50000-recipient limit")
    if not resolved.cors_origins or "*" in resolved.cors_origins:
        errors.append("CORS_ORIGINS must contain explicit HTTPS origins")
    elif any(urlparse(origin).scheme != "https" for origin in resolved.cors_origins):
        errors.append("every CORS origin must use HTTPS")
    if not resolved.trusted_hosts or "*" in resolved.trusted_hosts:
        errors.append("TRUSTED_HOSTS must contain explicit hostnames")
    if resolved.api_docs_enabled:
        errors.append("API_DOCS_ENABLED must be false")
    if resolved.email_delivery_backend != "service_bus":
        errors.append("EMAIL_DELIVERY_BACKEND must be service_bus")
    if not resolved.service_bus_fully_qualified_namespace:
        errors.append("SERVICE_BUS_FULLY_QUALIFIED_NAMESPACE is required")
    if not resolved.azure_key_vault_url:
        errors.append("AZURE_KEY_VAULT_URL is required")
    if not resolved.evidence_storage_account_url:
        errors.append("EVIDENCE_STORAGE_ACCOUNT_URL is required")
    if not resolved.evidence_storage_container:
        errors.append("EVIDENCE_STORAGE_CONTAINER is required")
    if resolved.lab_email_provider_enabled or resolved.lab_sms_provider_enabled:
        errors.append("lab outbound providers must be disabled")
    if resolved.ai_provider not in {"rule_based", "together"}:
        errors.append("AI_PROVIDER must be rule_based or together")
    if resolved.ai_provider == "together" and (
        not resolved.together_api_key or not resolved.together_api_key.get_secret_value().strip()
    ):
        errors.append("TOGETHER_API_KEY is required when AI_PROVIDER=together")
    if not resolved.together_model.strip():
        errors.append("TOGETHER_MODEL must not be empty")
    if not 1 <= resolved.together_timeout_seconds <= 120:
        errors.append("TOGETHER_TIMEOUT_SECONDS must be between 1 and 120")
    if not 0 <= resolved.together_max_retries <= 5:
        errors.append("TOGETHER_MAX_RETRIES must be between 0 and 5")
    if resolved.voice_clone_provider not in {"none", "elevenlabs"}:
        errors.append("VOICE_CLONE_PROVIDER must be none or elevenlabs")
    if resolved.video_clone_provider not in {"none", "did"}:
        errors.append("VIDEO_CLONE_PROVIDER must be none or did")
    if resolved.voice_clone_provider == "elevenlabs" and not resolved.elevenlabs_api_key:
        errors.append("ELEVENLABS_API_KEY is required when VOICE_CLONE_PROVIDER=elevenlabs")
    if resolved.video_clone_provider == "did" and not resolved.did_api_key:
        errors.append("DID_API_KEY is required when VIDEO_CLONE_PROVIDER=did")

    if errors:
        raise RuntimeError("Unsafe production configuration: " + "; ".join(errors))


@lru_cache
def get_settings() -> Settings:
    resolved = Settings()
    validate_production_settings(resolved)
    return resolved


settings = get_settings()


def secret_key_is_insecure() -> bool:
    """True when the JWT secret would not be safe outside local development."""
    return settings.secret_key == INSECURE_SECRET_PLACEHOLDER or len(settings.secret_key) < 32
