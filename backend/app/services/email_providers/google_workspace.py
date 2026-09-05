from __future__ import annotations

import base64
import json
from email.message import EmailMessage
from email.utils import formataddr

import httpx
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import service_account

from app.core.config import settings
from app.services.email_providers.base import EmailEnvelope, EmailProvider, ProviderError, SendResult
from app.services.secret_store import SecretStoreError, secret_store


class _BoundedGoogleAuthRequest(GoogleAuthRequest):
    def __call__(self, url, method="GET", body=None, headers=None, timeout=None, **kwargs):
        return super().__call__(
            url,
            method=method,
            body=body,
            headers=headers,
            timeout=settings.email_provider_timeout_seconds,
            **kwargs,
        )


class GoogleWorkspaceProvider(EmailProvider):
    def _access_token(self) -> str:
        if not self.connection.delegated_subject:
            raise ProviderError("Google delegated sender is missing", code="google_subject_missing", retryable=False)
        try:
            service_account_json = secret_store.get(self.connection.credential_secret_ref)
            info = json.loads(service_account_json)
            credentials = service_account.Credentials.from_service_account_info(
                info,
                scopes=["https://www.googleapis.com/auth/gmail.send"],
                subject=self.connection.delegated_subject,
            )
            transport = _BoundedGoogleAuthRequest()
            credentials.refresh(transport)
        except (SecretStoreError, ValueError, KeyError) as exc:
            raise ProviderError("Google service account is unavailable", code="google_secret_invalid", retryable=False) from exc
        except Exception as exc:
            raise ProviderError("Google authorization failed", code="google_auth_failed", retryable=True) from exc
        if not credentials.token:
            raise ProviderError("Google token response was invalid", code="google_token_invalid", retryable=True)
        return credentials.token

    def health_check(self) -> None:
        self._access_token()

    def send(self, envelope: EmailEnvelope) -> SendResult:
        message = EmailMessage()
        message["To"] = envelope.recipient
        message["From"] = formataddr((envelope.sender_name, envelope.sender_email))
        message["Subject"] = envelope.subject
        message["X-BreachSim-Attempt-ID"] = envelope.idempotency_key
        for key, value in envelope.headers.items():
            message[key] = value
        message.set_content(envelope.text_body)
        message.add_alternative(envelope.html_body, subtype="html")
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
        access_token = self._access_token()
        try:
            response = httpx.post(
                "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
                headers={"Authorization": f"Bearer {access_token}"},
                json={"raw": raw},
                timeout=settings.email_provider_timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            raise ProviderError(
                "Gmail submission timed out",
                code="gmail_send_timeout",
                retryable=False,
                outcome_unknown=True,
            ) from exc
        except httpx.NetworkError as exc:
            raise ProviderError(
                "Gmail submission outcome is unknown",
                code="gmail_network_error",
                retryable=False,
                outcome_unknown=True,
            ) from exc
        if response.status_code not in {200, 201}:
            retry_after = response.headers.get("Retry-After")
            raise ProviderError(
                "Gmail rejected the message",
                code=f"gmail_send_{response.status_code}",
                retryable=response.status_code >= 500 or response.status_code == 429,
                retry_after_seconds=int(retry_after) if retry_after and retry_after.isdigit() else None,
            )
        body = response.json()
        return SendResult(accepted=True, provider_message_id=body.get("id"), provider_status="accepted")
