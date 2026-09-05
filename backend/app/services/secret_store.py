from __future__ import annotations

import os
from functools import lru_cache

from app.core.config import settings


class SecretStoreError(RuntimeError):
    pass


class SecretStore:
    """Resolve secret references without persisting provider credentials in SQL."""

    def get(self, reference: str | None) -> str:
        if not reference:
            raise SecretStoreError("No secret reference is configured")
        if reference.startswith("env://"):
            name = reference.removeprefix("env://")
            value = os.getenv(name)
            if not value:
                raise SecretStoreError(f"Environment secret {name} is unavailable")
            return value
        if reference.startswith("kv://"):
            return self._get_key_vault_secret(reference.removeprefix("kv://"))
        raise SecretStoreError("Secret reference must use env:// or kv://")

    @staticmethod
    @lru_cache(maxsize=64)
    def _get_key_vault_secret(name: str) -> str:
        if not settings.azure_key_vault_url:
            raise SecretStoreError("AZURE_KEY_VAULT_URL is not configured")
        try:
            from azure.identity import DefaultAzureCredential
            from azure.keyvault.secrets import SecretClient

            client = SecretClient(
                vault_url=settings.azure_key_vault_url,
                credential=DefaultAzureCredential(exclude_interactive_browser_credential=True),
            )
            value = client.get_secret(name).value
        except Exception as exc:  # pragma: no cover - exercised against Azure in deployment tests
            raise SecretStoreError(f"Key Vault secret {name} could not be resolved") from exc
        if not value:
            raise SecretStoreError(f"Key Vault secret {name} is empty")
        return value


secret_store = SecretStore()
