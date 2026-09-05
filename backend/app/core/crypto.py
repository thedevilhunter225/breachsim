from __future__ import annotations

import base64
import hashlib
import hmac

from cryptography.fernet import Fernet

from app.core.config import settings


def get_fernet() -> Fernet:
    """Return the Fernet used for encrypted columns.

    No key is shipped in source. When ``BACKEND_ENCRYPTION_KEY`` is unset the key is
    derived from ``SECRET_KEY`` so local development and the test suite keep a stable
    key across restarts without a published constant to decrypt them. ``get_settings``
    refuses to start in production without an explicitly configured key.
    """
    key = settings.encryption_key or derive_static_key("column-encryption")
    return Fernet(key.encode("utf-8"))


def encrypt_text(value: str | None) -> str | None:
    if value is None:
        return None
    return get_fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_text(value: str | None) -> str | None:
    if value is None:
        return None
    return get_fernet().decrypt(value.encode("utf-8")).decode("utf-8")


def pseudonymous_id(*parts: str) -> str:
    secret = settings.secret_key.encode("utf-8")
    message = "::".join(parts).encode("utf-8")
    return hmac.new(secret, message, hashlib.sha256).hexdigest()


def blind_index(value: str, *, namespace: str) -> str:
    """Return a stable, tenant-independent lookup digest without exposing plaintext.

    The namespace prevents the same normalized value from producing the same index in
    unrelated columns. The application secret acts as a pepper, so a leaked database
    cannot be attacked with an unkeyed dictionary of common email addresses.
    """

    normalized = value.strip().casefold()
    return hmac.new(
        settings.secret_key.encode("utf-8"),
        f"blind-index:{namespace}:{normalized}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def derive_static_key(label: str) -> str:
    digest = hashlib.sha256(f"{settings.secret_key}:{label}".encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).decode("utf-8")
