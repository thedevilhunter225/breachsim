from __future__ import annotations

import base64
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from app.core.config import settings

ALGORITHM = "HS256"


def hash_password(password: str, *, salt: bytes | None = None) -> str:
    local_salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), local_salt, 120_000)
    return f"{base64.b64encode(local_salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password: str, stored_hash: str) -> bool:
    salt_b64, digest_b64 = stored_hash.split("$", 1)
    salt = base64.b64decode(salt_b64.encode("utf-8"))
    expected = base64.b64decode(digest_b64.encode("utf-8"))
    actual = base64.b64decode(hash_password(password, salt=salt).split("$", 1)[1].encode("utf-8"))
    return hmac.compare_digest(actual, expected)


def create_access_token(subject: str, *, expires_delta: timedelta | None = None, extra: dict[str, Any] | None = None) -> str:
    payload: dict[str, Any] = {"sub": subject}
    payload["exp"] = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
