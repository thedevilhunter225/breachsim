"""Outbound SMS adapter for the smishing channel.

The gateway speaks the Twilio ``Messages`` REST shape, which most providers (Twilio,
Vonage compatibility layers, and self-hosted gateways such as Kannel behind a shim)
either implement natively or can be pointed at. Configuration lives on the organization
so a lab can run against a sandbox number without touching application settings.

Every send is gated twice: the provider must be explicitly enabled *and* the recipient
number must appear on the organization allowlist. There is deliberately no way to send
to an arbitrary number from the UI.
"""

from __future__ import annotations

import re

import httpx
from fastapi import HTTPException, status

from app.models.entities import Organization
from app.schemas.integrations import SmsIntegrationRead, SmsIntegrationUpdate

DEFAULT_SMS_API_BASE_URL = "https://api.twilio.com/2010-04-01"


def normalize_number(value: str | None) -> str:
    """Reduce a phone number to digits (plus leading +) so allowlist checks are stable."""
    if not value:
        return ""
    cleaned = re.sub(r"[^\d+]", "", value.strip())
    if cleaned.startswith("00"):
        cleaned = f"+{cleaned[2:]}"
    return cleaned


def serialize_sms_integration(org: Organization) -> SmsIntegrationRead:
    return SmsIntegrationRead(
        sms_provider_enabled=org.sms_provider_enabled,
        sms_provider_mode=org.sms_provider_mode,
        sms_api_base_url=org.sms_api_base_url or DEFAULT_SMS_API_BASE_URL,
        sms_account_sid=org.sms_account_sid,
        sms_from_number=org.sms_from_number,
        sms_recipient_allowlist=org.sms_recipient_allowlist or [],
        has_auth_token=bool(org.sms_auth_token),
    )


def update_sms_integration(org: Organization, payload: SmsIntegrationUpdate) -> Organization:
    org.sms_provider_enabled = payload.sms_provider_enabled
    org.sms_provider_mode = payload.sms_provider_mode
    org.sms_api_base_url = payload.sms_api_base_url or DEFAULT_SMS_API_BASE_URL
    org.sms_account_sid = payload.sms_account_sid
    if payload.sms_auth_token:
        org.sms_auth_token = payload.sms_auth_token
    org.sms_from_number = normalize_number(payload.sms_from_number)
    org.sms_recipient_allowlist = [normalize_number(number) for number in payload.sms_recipient_allowlist if number]
    return org


def validate_sms_delivery_setup(org: Organization) -> None:
    if not org.sms_provider_enabled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Lab SMS provider is disabled")
    if org.sms_provider_mode != "lab":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="SMS provider mode must be 'lab'")
    missing = [
        field
        for field, value in {
            "sms_account_sid": org.sms_account_sid,
            "sms_auth_token": org.sms_auth_token,
            "sms_from_number": org.sms_from_number,
        }.items()
        if not value
    ]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Missing SMS settings: {', '.join(missing)}",
        )


def ensure_sms_recipient_allowed(org: Organization, recipient: str | None) -> str:
    number = normalize_number(recipient)
    if not number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Employee has no phone number on file for SMS delivery",
        )
    allowlist = {normalize_number(entry) for entry in (org.sms_recipient_allowlist or [])}
    if number not in allowlist:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Recipient {number} is not in the lab SMS allowlist",
        )
    return number


def send_lab_sms(*, org: Organization, recipient: str | None, body_text: str, cta_url: str) -> str:
    """Send one simulation SMS and return the provider message id."""
    validate_sms_delivery_setup(org)
    number = ensure_sms_recipient_allowed(org, recipient)

    base_url = (org.sms_api_base_url or DEFAULT_SMS_API_BASE_URL).rstrip("/")
    endpoint = f"{base_url}/Accounts/{org.sms_account_sid}/Messages.json"
    message_body = f"{body_text.strip()} {cta_url}".strip()

    try:
        response = httpx.post(
            endpoint,
            auth=(org.sms_account_sid, org.sms_auth_token),
            data={"From": org.sms_from_number, "To": number, "Body": message_body},
            timeout=30.0,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:300] if exc.response is not None else str(exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"SMS gateway rejected the message: {detail}",
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"SMS gateway request failed: {exc}",
        ) from exc

    try:
        return str(response.json().get("sid") or "")
    except ValueError:
        return ""
