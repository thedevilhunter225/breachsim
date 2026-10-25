"""SMS adapters for the legacy campaign lab and a fixed, link-free Android demo.

The legacy campaign adapter speaks the Twilio ``Messages`` REST shape. The separate
Android demo adapter speaks SMSGate's local API and cannot send campaign copy or links.
Configuration lives on the organization rather than application-wide settings.

Every send is gated twice: the provider must be explicitly enabled *and* the recipient
number must appear on the organization allowlist. There is deliberately no way to send
to an arbitrary number from the UI.
"""

from __future__ import annotations

import ipaddress
import re
from urllib.parse import urlsplit

import httpx
from fastapi import HTTPException, status

from app.models.entities import Organization
from app.schemas.integrations import SmsIntegrationRead, SmsIntegrationUpdate

DEFAULT_SMS_API_BASE_URL = "https://api.twilio.com/2010-04-01"
ANDROID_DEMO_MESSAGE = (
    "BreachSim simulation - IT Service Desk: A sign-in request needs review. "
    "Verify with IT through your usual channel; never share a code by text."
)
_PAKISTAN_MOBILE = re.compile(r"^\+923\d{9}$")
_LOCAL_NETWORKS = tuple(
    ipaddress.ip_network(cidr) for cidr in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")
)


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
        sms_api_base_url=org.sms_api_base_url or (None if org.sms_provider_mode == "android_demo" else DEFAULT_SMS_API_BASE_URL),
        sms_account_sid=org.sms_account_sid,
        sms_from_number=org.sms_from_number,
        sms_recipient_allowlist=org.sms_recipient_allowlist or [],
        has_auth_token=bool(org.sms_auth_token),
    )


def update_sms_integration(org: Organization, payload: SmsIntegrationUpdate) -> Organization:
    if payload.sms_provider_mode not in {"sandbox", "lab", "android_demo"}:
        raise HTTPException(status_code=400, detail="Unsupported SMS provider mode")
    previous_mode = org.sms_provider_mode
    org.sms_provider_enabled = payload.sms_provider_enabled
    org.sms_provider_mode = payload.sms_provider_mode
    org.sms_api_base_url = payload.sms_api_base_url or (
        None if payload.sms_provider_mode == "android_demo" else DEFAULT_SMS_API_BASE_URL
    )
    org.sms_account_sid = payload.sms_account_sid
    if payload.sms_auth_token:
        org.sms_auth_token = payload.sms_auth_token
    elif previous_mode != payload.sms_provider_mode:
        org.sms_auth_token = None
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


def _android_gateway_url(value: str | None) -> str:
    """Accept only a phone's literal LAN address; never proxy to arbitrary hosts."""
    parsed = urlsplit((value or "").strip())
    try:
        address = ipaddress.IPv4Address(parsed.hostname or "")
        port = parsed.port
    except (ValueError, AttributeError) as exc:
        raise HTTPException(status_code=400, detail="Android gateway URL must use a private IPv4 address") from exc
    if (
        parsed.scheme != "http"
        or port != 8080
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
        or not any(address in network for network in _LOCAL_NETWORKS)
    ):
        raise HTTPException(status_code=400, detail="Android gateway URL must be http://<phone-LAN-IP>:8080")
    return f"http://{address}:8080"


def send_android_demo_sms(*, org: Organization, recipient: str) -> str:
    """Queue one fixed, link-free demo SMS through SMSGate's local Android API."""
    if not org.sms_provider_enabled or org.sms_provider_mode != "android_demo":
        raise HTTPException(status_code=400, detail="Android SMS demo is not enabled")
    allowlist = {normalize_number(number) for number in (org.sms_recipient_allowlist or [])}
    if not allowlist or len(allowlist) > 4 or not all(_PAKISTAN_MOBILE.fullmatch(number) for number in allowlist):
        raise HTTPException(status_code=400, detail="Android demo requires 1–4 Pakistani mobile numbers in E.164 format")
    number = ensure_sms_recipient_allowed(org, recipient)
    if not org.sms_account_sid or not org.sms_auth_token:
        raise HTTPException(status_code=400, detail="Android gateway username and password are required")
    endpoint = f"{_android_gateway_url(org.sms_api_base_url)}/message"
    try:
        response = httpx.post(
            endpoint,
            auth=(org.sms_account_sid, org.sms_auth_token),
            json={"textMessage": {"text": ANDROID_DEMO_MESSAGE}, "phoneNumbers": [number]},
            timeout=8.0,
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(status_code=502, detail="Android SMS gateway did not accept the demo message") from exc
    message_id = payload.get("id") if isinstance(payload, dict) else None
    if not isinstance(message_id, str) or not message_id.strip():
        raise HTTPException(status_code=502, detail="Android SMS gateway returned no message ID")
    return message_id


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
