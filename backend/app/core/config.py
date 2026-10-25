from __future__ import annotations

import base64
import hashlib
import ipaddress
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
    #: Off unless explicitly enabled, so configuring a provider key never enables cloning.
    elevenlabs_allow_voice_cloning: bool = False

    video_clone_provider: str = "none"  # none | did
    did_api_key: str | None = None
    did_base_url: str = "https://api.d-id.com"

    #: Launch-policy approval for real voice/video cloning in production. The initial
    #: production release excludes synthetic media, so a production process refuses to
    #: start with a clone provider configured until this is deliberately set to true.
    synthetic_media_production_approved: bool = False


#: Shipped placeholder. Signing tokens with a publicly-known secret means anyone can
#: forge an admin token, which defeats every RBAC check in the product.
INSECURE_SECRET_PLACEHOLDER = "change-me-in-production"

#: SHA-256 fingerprints (see ``encryption_key_fingerprint``) of Fernet keys that were
#: committed to this repository's git history. The initial commit 2578f4b shipped one as
#: the ENCRYPTION_KEY default in backend/app/core/config.py, .env.example and
#: docker-compose.yml; fba4490 removed it, but anyone with a clone can still read it and
#: decrypt every field it protected. Production refuses these keys and other environments
#: log a SECURITY warning. Store digests only: never put a key's text in this file.
COMPROMISED_ENCRYPTION_KEY_SHA256 = frozenset(
    {
        "61c9dc46c03199e3968e3e7afc84d6a33bc0af82d1272dafc2d91262e6a62374",
    }
)

#: Hostnames that only make sense on a developer machine or in the test client. A production
#: Host or CORS allowlist containing one trusts requests that never passed through the edge.
LOOPBACK_OR_TEST_HOSTNAMES = frozenset({"localhost", "127.0.0.1", "::1", "[::1]", "0.0.0.0", "testserver"})


def is_production_environment(environment: str) -> bool:
    return environment.lower() in {"production", "prod"}


def encryption_key_fingerprint(key: str) -> str | None:
    """Return the SHA-256 hex digest of a Fernet key's canonical text, or None if it is not one.

    Fernet decodes keys leniently (whitespace and characters outside the base64 alphabet are
    dropped), so the key is canonicalised first. Otherwise a reformatted copy of a denylisted
    key would decrypt the same data while slipping past the denylist.
    """
    try:
        raw = base64.urlsafe_b64decode(key.encode("utf-8"))
    except ValueError:
        return None
    if len(raw) != 32:
        return None
    return hashlib.sha256(base64.urlsafe_b64encode(raw)).hexdigest()


def is_compromised_encryption_key(key: str | None) -> bool:
    if not key:
        return False
    return encryption_key_fingerprint(key) in COMPROMISED_ENCRYPTION_KEY_SHA256


def is_loopback_or_test_host(host: str | None) -> bool:
    """True for localhost, loopback/unspecified addresses and the test client, with or without a port."""
    name = (host or "").strip().lower().rstrip(".")
    if name.startswith("[") and "]" in name:
        name = name[: name.index("]") + 1]  # "[::1]:8000" -> "[::1]"
    elif name.count(":") == 1:
        name = name.partition(":")[0]  # "localhost:3000" -> "localhost"
    if name in LOOPBACK_OR_TEST_HOSTNAMES or name.endswith(".localhost"):
        return True
    try:
        address = ipaddress.ip_address(name.strip("[]"))
    except ValueError:
        return False
    return address.is_loopback or address.is_unspecified


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
        else:
            if is_compromised_encryption_key(resolved.encryption_key):
                errors.append(
                    "ENCRYPTION_KEY was committed to this repository's git history and is compromised; "
                    "generate a new Fernet key and re-encrypt existing data"
                )
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
    loopback_origins = [
        origin for origin in resolved.cors_origins if is_loopback_or_test_host(urlparse(origin).hostname)
    ]
    if loopback_origins:
        errors.append(
            f"CORS_ORIGINS must not contain loopback or test hostnames (found: {', '.join(loopback_origins)})"
        )
    if not resolved.trusted_hosts or "*" in resolved.trusted_hosts:
        errors.append("TRUSTED_HOSTS must contain explicit hostnames")
    loopback_hosts = [host for host in resolved.trusted_hosts if is_loopback_or_test_host(host)]
    if loopback_hosts:
        errors.append(f"TRUSTED_HOSTS must not contain loopback or test hostnames (found: {', '.join(loopback_hosts)})")
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
    clone_providers = {
        (provider or "none").strip().lower()
        for provider in (resolved.voice_clone_provider, resolved.video_clone_provider)
    }
    if not resolved.synthetic_media_production_approved and clone_providers != {"none"}:
        errors.append(
            "VOICE_CLONE_PROVIDER and VIDEO_CLONE_PROVIDER must both be none: the initial production launch "
            "policy excludes synthetic voice/video cloning (set SYNTHETIC_MEDIA_PRODUCTION_APPROVED=true only "
            "after that policy is formally revised and approved)"
        )
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


def encryption_key_is_compromised() -> bool:
    """True when ENCRYPTION_KEY is a key that was published in this repository's git history."""
    return is_compromised_encryption_key(settings.encryption_key)
