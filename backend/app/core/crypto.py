from __future__ import annotations

import base64
import hashlib
import hmac

from cryptography.fernet import Fernet

from app.core.config import settings


def get_fernet() -> Fernet:
    key = settings.encryption_key.encode("utf-8")
    return Fernet(key)


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


def derive_static_key(label: str) -> str:
    digest = hashlib.sha256(f"{settings.secret_key}:{label}".encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).decode("utf-8")
