from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.types import TypeDecorator

from app.core.crypto import decrypt_text, encrypt_text


class EncryptedString(TypeDecorator):
    impl = String
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect: object) -> str | None:
        return encrypt_text(value)

    def process_result_value(self, value: str | None, dialect: object) -> str | None:
        return decrypt_text(value)
