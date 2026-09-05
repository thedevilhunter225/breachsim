from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass

from app.core.config import settings


@dataclass(frozen=True)
class IssuedPublicToken:
    public_id: str
    secret: str

    @property
    def value(self) -> str:
        return f"{self.public_id}.{self.secret}"


def issue_public_token() -> IssuedPublicToken:
    return IssuedPublicToken(
        public_id=secrets.token_urlsafe(12),
        secret=secrets.token_urlsafe(32),
    )


def hash_token_secret(secret: str) -> str:
    return hmac.new(
        settings.secret_key.encode("utf-8"),
        f"public-token:{secret}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def parse_public_token(value: str) -> tuple[str, str] | None:
    public_id, separator, secret = value.partition(".")
    if separator != "." or not 8 <= len(public_id) <= 32 or not 20 <= len(secret) <= 128:
        return None
    return public_id, secret


def token_secret_matches(secret: str, expected_hash: str | None) -> bool:
    if not expected_hash:
        return False
    return hmac.compare_digest(hash_token_secret(secret), expected_hash)
