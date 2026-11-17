from __future__ import annotations

import base64
import secrets
from io import BytesIO

import pyotp
import qrcode

from app.core.config import settings
from app.services.public_tokens import hash_token_secret


def issue_mfa_material(email: str) -> tuple[str, str, list[str], list[str]]:
    secret = pyotp.random_base32()
    provisioning_uri = pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=settings.app_name)
    recovery_codes = [f"{secrets.token_hex(4)}-{secrets.token_hex(4)}" for _ in range(10)]
    recovery_hashes = [hash_token_secret(code) for code in recovery_codes]
    return secret, provisioning_uri, recovery_codes, recovery_hashes


def provisioning_qr_data_url(provisioning_uri: str) -> str:
    """The provisioning URI as a PNG data URL an authenticator app can scan."""
    buffer = BytesIO()
    qrcode.make(provisioning_uri).save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def verify_totp_code(secret: str, code: str) -> bool:
    """Accept an authenticator code only.

    Used to confirm a new enrollment. A recovery code would prove nothing there: it was
    issued alongside the secret and says nothing about whether the authenticator works.
    """
    normalized = code.strip().replace(" ", "")
    if not (normalized.isdigit() and len(normalized) == 6):
        return False
    return bool(pyotp.TOTP(secret).verify(normalized, valid_window=1))


def verify_mfa_code(user, code: str) -> bool:
    normalized = code.strip().replace(" ", "")
    if user.mfa_secret and normalized.isdigit() and len(normalized) == 6:
        if pyotp.TOTP(user.mfa_secret).verify(normalized, valid_window=1):
            return True
    expected = hash_token_secret(code.strip().casefold())
    if expected in (user.mfa_recovery_hashes or []):
        user.mfa_recovery_hashes = [value for value in user.mfa_recovery_hashes if value != expected]
        return True
    return False
