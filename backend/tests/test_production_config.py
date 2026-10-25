from __future__ import annotations

import logging
import re

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from app.core import config
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


def test_synthetic_media_and_voice_cloning_are_off_by_default(monkeypatch):
    for name in (
        "VOICE_CLONE_PROVIDER",
        "VIDEO_CLONE_PROVIDER",
        "ELEVENLABS_ALLOW_VOICE_CLONING",
        "SYNTHETIC_MEDIA_PRODUCTION_APPROVED",
    ):
        monkeypatch.delenv(name, raising=False)
    defaults = Settings(_env_file=None)

    assert defaults.voice_clone_provider == "none"
    assert defaults.video_clone_provider == "none"
    assert defaults.elevenlabs_allow_voice_cloning is False
    assert defaults.synthetic_media_production_approved is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"voice_clone_provider": "elevenlabs", "elevenlabs_api_key": "elevenlabs-test-key"},
        {"video_clone_provider": "did", "did_api_key": "did-test-key"},
        {"voice_clone_provider": " ElevenLabs ", "elevenlabs_api_key": "elevenlabs-test-key"},
    ],
)
def test_synthetic_media_is_refused_in_production_without_launch_approval(overrides):
    with pytest.raises(RuntimeError) as exc:
        validate_production_settings(production_settings(**overrides))

    message = str(exc.value)
    assert "VOICE_CLONE_PROVIDER and VIDEO_CLONE_PROVIDER must both be none" in message
    assert "launch policy" in message
    assert "SYNTHETIC_MEDIA_PRODUCTION_APPROVED=true" in message


def test_synthetic_media_can_be_enabled_in_production_after_explicit_approval():
    validate_production_settings(
        production_settings(
            synthetic_media_production_approved=True,
            voice_clone_provider="elevenlabs",
            elevenlabs_api_key="elevenlabs-test-key",
            video_clone_provider="did",
            did_api_key="did-test-key",
        )
    )


def test_approved_synthetic_media_still_requires_provider_keys():
    with pytest.raises(RuntimeError) as exc:
        validate_production_settings(
            production_settings(
                synthetic_media_production_approved=True,
                voice_clone_provider="elevenlabs",
                video_clone_provider="did",
            )
        )

    message = str(exc.value)
    assert "ELEVENLABS_API_KEY is required" in message
    assert "DID_API_KEY is required" in message
    assert "must both be none" not in message


@pytest.mark.parametrize(
    "host",
    [
        "localhost",
        "LOCALHOST",
        "localhost:8000",
        "127.0.0.1",
        "127.0.0.2",
        "::1",
        "[::1]",
        "0.0.0.0",
        "testserver",
        "api.localhost",
    ],
)
def test_loopback_and_test_trusted_hosts_are_refused_in_production(host):
    with pytest.raises(RuntimeError, match="TRUSTED_HOSTS must not contain loopback or test hostnames"):
        validate_production_settings(production_settings(trusted_hosts=["breachsim.example.com", "backend", host]))


@pytest.mark.parametrize(
    "origin",
    [
        "https://localhost",
        "https://LocalHost:3000",
        "https://127.0.0.1:3001",
        "https://[::1]:3000",
        "https://0.0.0.0",
        "https://testserver",
    ],
)
def test_loopback_cors_origins_are_refused_in_production(origin):
    with pytest.raises(RuntimeError, match="CORS_ORIGINS must not contain loopback or test hostnames"):
        validate_production_settings(production_settings(cors_origins=["https://breachsim.example.com", origin]))


def test_hostnames_that_merely_contain_localhost_are_accepted():
    validate_production_settings(
        production_settings(
            trusted_hosts=["breachsim.example.com", "backend", "localhost-gateway.example.com"],
            cors_origins=["https://breachsim.example.com", "https://app.localhosting.example.com"],
        )
    )


def deny_encryption_keys(monkeypatch, *keys: str) -> None:
    """Swap the committed-key denylist for fingerprints of freshly generated test keys."""
    monkeypatch.setattr(
        config,
        "COMPROMISED_ENCRYPTION_KEY_SHA256",
        frozenset(config.encryption_key_fingerprint(key) for key in keys),
    )


def test_compromised_key_denylist_stores_only_sha256_digests():
    assert config.COMPROMISED_ENCRYPTION_KEY_SHA256
    for digest in config.COMPROMISED_ENCRYPTION_KEY_SHA256:
        assert re.fullmatch(r"[0-9a-f]{64}", digest)


def test_denylisted_encryption_key_is_refused_in_production(monkeypatch):
    key = Fernet.generate_key().decode("utf-8")
    deny_encryption_keys(monkeypatch, key)

    with pytest.raises(RuntimeError, match="ENCRYPTION_KEY was committed to this repository's git history"):
        validate_production_settings(production_settings(encryption_key=key))
    # A different, freshly generated key is still accepted.
    validate_production_settings(production_settings(encryption_key=Fernet.generate_key().decode("utf-8")))


@pytest.mark.parametrize(
    "reformat",
    [
        lambda key: f" {key}\n",
        lambda key: key[:22] + "\n" + key[22:],
        lambda key: key.replace("-", "+").replace("_", "/"),
    ],
    ids=["surrounding-whitespace", "embedded-newline", "standard-base64-alphabet"],
)
def test_reformatted_denylisted_encryption_key_is_still_refused(monkeypatch, reformat):
    key = Fernet.generate_key().decode("utf-8")
    deny_encryption_keys(monkeypatch, key)
    variant = reformat(key)
    # Fernet still accepts the variant as the same key, so it must not slip past the denylist.
    token = Fernet(key.encode("utf-8")).encrypt(b"probe")
    assert Fernet(variant.encode("utf-8")).decrypt(token) == b"probe"

    with pytest.raises(RuntimeError, match="ENCRYPTION_KEY was committed to this repository's git history"):
        validate_production_settings(production_settings(encryption_key=variant))


def test_denylisted_encryption_key_only_warns_outside_production(monkeypatch, caplog):
    key = Fernet.generate_key().decode("utf-8")
    deny_encryption_keys(monkeypatch, key)
    validate_production_settings(Settings(_env_file=None, environment="development", encryption_key=key))

    original_key = config.settings.encryption_key
    monkeypatch.setattr(config.settings, "encryption_key", key)
    assert config.encryption_key_is_compromised()
    monkeypatch.setattr(config.settings, "encryption_key", Fernet.generate_key().decode("utf-8"))
    assert not config.encryption_key_is_compromised()
    # Restore the real key before the app starts: init_db may encrypt seed data with it.
    monkeypatch.setattr(config.settings, "encryption_key", original_key)

    from app import main

    monkeypatch.setattr(main, "encryption_key_is_compromised", lambda: True)
    with caplog.at_level(logging.WARNING, logger="uvicorn.error"):
        with TestClient(main.app):
            pass
    assert "SECURITY: ENCRYPTION_KEY is a key that was committed to this repository's git history" in caplog.text
