from __future__ import annotations

import smtplib
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from html import escape

from fastapi import HTTPException, status

from app.models.entities import Organization
from app.schemas.integrations import EmailIntegrationRead, EmailIntegrationUpdate


def serialize_email_integration(org: Organization) -> EmailIntegrationRead:
    return EmailIntegrationRead(
        email_provider_enabled=org.email_provider_enabled,
        email_provider_mode=org.email_provider_mode,
        smtp_host=org.smtp_host,
        smtp_port=org.smtp_port,
        smtp_username=org.smtp_username,
        smtp_from_email=org.smtp_from_email,
        smtp_sender_name=org.smtp_sender_name,
        smtp_recipient_allowlist=org.smtp_recipient_allowlist or [],
        has_password=bool(org.smtp_password),
    )


def update_email_integration(org: Organization, payload: EmailIntegrationUpdate) -> Organization:
    org.email_provider_enabled = payload.email_provider_enabled
    org.email_provider_mode = payload.email_provider_mode
    org.smtp_host = payload.smtp_host
    org.smtp_port = payload.smtp_port
    org.smtp_username = payload.smtp_username
    if payload.smtp_password:
        org.smtp_password = payload.smtp_password
    org.smtp_from_email = payload.smtp_from_email
    org.smtp_sender_name = payload.smtp_sender_name
    org.smtp_recipient_allowlist = [str(address).lower() for address in payload.smtp_recipient_allowlist]
    return org


def validate_email_delivery_setup(org: Organization) -> None:
    if not org.email_provider_enabled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Lab email provider is disabled")
    if org.email_provider_mode != "lab":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email provider mode must be 'lab'")
    missing = [field for field, value in {
        "smtp_host": org.smtp_host,
        "smtp_username": org.smtp_username,
        "smtp_password": org.smtp_password,
        "smtp_from_email": org.smtp_from_email,
    }.items() if not value]
    if missing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Missing email settings: {', '.join(missing)}")


def ensure_recipient_allowed(org: Organization, recipient: str) -> None:
    allowlist = {address.lower() for address in (org.smtp_recipient_allowlist or [])}
    if recipient.lower() not in allowlist:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Recipient {recipient} is not in the lab allowlist")


def send_lab_email(
    *,
    org: Organization,
    recipient: str,
    subject: str,
    body_text: str,
    cta_url: str,
    cta_text: str = "clickhere",
    html_body: str | None = None,
    attachments: list[tuple[str, bytes, str, str]] | None = None,
    inline_images: list[tuple[str | None, bytes, str, str, str]] | None = None,
) -> None:
    validate_email_delivery_setup(org)
    ensure_recipient_allowed(org, recipient)

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = f"{org.smtp_sender_name or 'Workflow Notifications'} <{org.smtp_from_email}>"
    message["To"] = recipient
    message["Reply-To"] = org.smtp_from_email
    message["Date"] = formatdate(localtime=True)
    message["Message-ID"] = make_msgid(domain=org.smtp_from_email.rpartition("@")[2] or None)
    message.set_content(
        f"{body_text}\n\n{cta_text}: {cta_url}"
    )
    safe_body = escape(body_text).replace(chr(10), "<br>")
    safe_cta_url = escape(cta_url, quote=True)
    safe_cta_text = escape(cta_text)
    message.add_alternative(
        html_body
        or f"""
        <html>
          <body style="font-family:Arial,sans-serif;color:#111827;line-height:1.55">
            <div style="max-width:640px">
              {safe_body}
              <p style="margin-top:20px">
                <a href="{safe_cta_url}" style="color:#0f5cc0;font-weight:600">{safe_cta_text}</a>
              </p>
            </div>
          </body>
        </html>
        """,
        subtype="html",
    )
    html_part = message.get_body(preferencelist=("html",))
    if html_part is not None:
        for filename, content, maintype, subtype, content_id in inline_images or []:
            related_headers = {
                "maintype": maintype,
                "subtype": subtype,
                "cid": f"<{content_id}>",
                "disposition": "inline",
            }
            if filename:
                related_headers["filename"] = filename
            html_part.add_related(content, **related_headers)
    for filename, content, maintype, subtype in attachments or []:
        message.add_attachment(content, maintype=maintype, subtype=subtype, filename=filename)

    with smtplib.SMTP(org.smtp_host, org.smtp_port, timeout=20) as server:
        server.starttls()
        server.login(org.smtp_username, org.smtp_password)
        server.send_message(message)
