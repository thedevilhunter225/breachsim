from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

from app.core.config import Settings, validate_production_settings


def production_settings(**overrides) -> Settings:
    values = {
        "environment": "production",
        "secret_key": "s" * 64,
        "encryption_key": Fernet.generate_key().decode("utf-8"),
        "database_url": "postgresql+psycopg://user:pass@postgres/breachsim",
        "redis_url": "redis://:pass@redis:6379/0",
        "frontend_base_url": "https://breachsim.example.com",
        "public_url_scheme": "https",
        "platform_training_domain": "training.example.com",
        "front_door_id": "11111111-1111-1111-1111-111111111111",
        "front_door_endpoint_hostname": "breachsim.azurefd.net",
        "cors_origins": ["https://breachsim.example.com"],
        "trusted_hosts": ["breachsim.example.com", "backend"],
        "access_token_expire_minutes": 30,
        "session_cookie_secure": True,
        "email_delivery_backend": "service_bus",
        "service_bus_fully_qualified_namespace": "breachsim.servicebus.windows.net",
        "azure_key_vault_url": "https://breachsim-kv.vault.azure.net/",
        "evidence_storage_account_url": "https://breachsimevidence.blob.core.windows.net/",
        "evidence_storage_container": "audit-evidence",
        "seed_demo_content": False,
        "api_docs_enabled": False,
        "ai_provider": "rule_based",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_safe_production_configuration_is_accepted():
    validate_production_settings(production_settings())


def test_unsafe_production_configuration_fails_closed():
    settings = production_settings(
        secret_key="short",
        encryption_key="not-a-fernet-key",
        database_url="sqlite:///production.db",
        frontend_base_url="http://example.com",
        cors_origins=["*"],
        trusted_hosts=["*"],
        access_token_expire_minutes=480,
        seed_demo_content=True,
    )
    with pytest.raises(RuntimeError) as exc:
        validate_production_settings(settings)

    message = str(exc.value)
    assert "SECRET_KEY" in message
    assert "ENCRYPTION_KEY" in message
    assert "PostgreSQL" in message
    assert "SEED_DEMO_CONTENT" in message
    assert "HTTPS" in message


def test_together_production_configuration_requires_api_key():
    with pytest.raises(RuntimeError, match="TOGETHER_API_KEY"):
        validate_production_settings(
            production_settings(ai_provider="together", together_api_key=None)
        )


def test_together_production_configuration_accepts_api_key():
    validate_production_settings(
        production_settings(ai_provider="together", together_api_key="together-test-key")
    )
