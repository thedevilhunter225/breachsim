from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from app.core.config import settings

ALGORITHM = "HS256"
PASSWORD_SCHEME = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 600_000
LEGACY_PASSWORD_ITERATIONS = 120_000


def password_is_strong(password: str) -> bool:
    return (
        len(password) >= 14
        and bool(re.search(r"[a-z]", password))
        and bool(re.search(r"[A-Z]", password))
        and bool(re.search(r"\d", password))
        and bool(re.search(r"[^A-Za-z0-9]", password))
    )


def hash_password(password: str, *, salt: bytes | None = None, iterations: int = PASSWORD_ITERATIONS) -> str:
    local_salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), local_salt, iterations)
    return "$".join(
        (
            PASSWORD_SCHEME,
            str(iterations),
            base64.b64encode(local_salt).decode(),
            base64.b64encode(digest).decode(),
        )
    )


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        parts = stored_hash.split("$")
        if len(parts) == 4 and parts[0] == PASSWORD_SCHEME:
            iterations = int(parts[1])
            salt_b64, digest_b64 = parts[2], parts[3]
        elif len(parts) == 2:
            iterations = LEGACY_PASSWORD_ITERATIONS
            salt_b64, digest_b64 = parts
        else:
            return False
        salt = base64.b64decode(salt_b64.encode("utf-8"))
        expected = base64.b64decode(digest_b64.encode("utf-8"))
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(actual, expected)
    except (TypeError, ValueError):
        return False


def password_needs_rehash(stored_hash: str) -> bool:
    parts = stored_hash.split("$")
    return not (
        len(parts) == 4
        and parts[0] == PASSWORD_SCHEME
        and parts[1].isdigit()
        and int(parts[1]) >= PASSWORD_ITERATIONS
    )


def create_access_token(
    subject: str,
    *,
    token_id: str | None = None,
    expires_delta: timedelta | None = None,
    extra: dict[str, Any] | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "jti": token_id or secrets.token_urlsafe(24),
        "iss": settings.access_token_issuer,
        "aud": settings.access_token_audience,
        "iat": now,
        "nbf": now,
        "exp": now + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes)),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    return jwt.decode(
        token,
        settings.secret_key,
        algorithms=[ALGORITHM],
        issuer=settings.access_token_issuer,
        audience=settings.access_token_audience,
        options={"require": ["sub", "jti", "iss", "aud", "iat", "nbf", "exp"]},
    )
