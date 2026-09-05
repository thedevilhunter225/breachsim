from __future__ import annotations

from email.header import Header

import httpx

from app.core.config import settings
from app.services.email_providers.base import EmailEnvelope, EmailProvider, ProviderError, SendResult
from app.services.secret_store import SecretStoreError, secret_store


class MicrosoftGraphProvider(EmailProvider):
    def _access_token(self) -> str:
        if not settings.microsoft_graph_client_id or not self.connection.customer_tenant_id:
            raise ProviderError(
                "Microsoft Graph application or customer tenant is not configured",
                code="graph_not_configured",
                retryable=False,
            )
        try:
            client_secret = secret_store.get(self.connection.credential_secret_ref)
        except SecretStoreError as exc:
            raise ProviderError(str(exc), code="secret_unavailable", retryable=True) from exc
        try:
            response = httpx.post(
                f"https://login.microsoftonline.com/{self.connection.customer_tenant_id}/oauth2/v2.0/token",
                data={
                    "client_id": settings.microsoft_graph_client_id,
                    "client_secret": client_secret,
                    "scope": "https://graph.microsoft.com/.default",
                    "grant_type": "client_credentials",
                },
                timeout=settings.email_provider_timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            raise ProviderError("Microsoft token request timed out", code="token_timeout", retryable=True) from exc
        if response.status_code >= 400:
            raise ProviderError(
                "Microsoft authorization failed",
                code=f"graph_token_{response.status_code}",
                retryable=response.status_code >= 500 or response.status_code == 429,
                retry_after_seconds=_retry_after(response),
            )
        token = response.json().get("access_token")
        if not token:
            raise ProviderError("Microsoft token response was invalid", code="invalid_token_response", retryable=True)
        return token

    def health_check(self) -> None:
        self._access_token()

    def send(self, envelope: EmailEnvelope) -> SendResult:
        access_token = self._access_token()
        headers = [
            {"name": "X-BreachSim-Attempt-ID", "value": envelope.idempotency_key},
            *({"name": key, "value": value} for key, value in envelope.headers.items()),
        ]
        payload = {
            "message": {
                "subject": str(Header(envelope.subject, "utf-8")),
                "body": {"contentType": "HTML", "content": envelope.html_body},
                "toRecipients": [{"emailAddress": {"address": envelope.recipient}}],
                "internetMessageHeaders": headers,
            },
            "saveToSentItems": True,
        }
        url = f"https://graph.microsoft.com/v1.0/users/{self.connection.sender_email}/sendMail"
        try:
            response = httpx.post(
                url,
                headers={"Authorization": f"Bearer {access_token}"},
                json=payload,
                timeout=settings.email_provider_timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            # Graph may have accepted the request before the timeout. Retrying without a
            # provider idempotency guarantee could send a duplicate.
            raise ProviderError(
                "Microsoft Graph submission timed out",
                code="graph_send_timeout",
                retryable=False,
                outcome_unknown=True,
            ) from exc
        except httpx.NetworkError as exc:
            raise ProviderError(
                "Microsoft Graph submission outcome is unknown",
                code="graph_network_error",
                retryable=False,
                outcome_unknown=True,
            ) from exc
        if response.status_code != 202:
            raise ProviderError(
                "Microsoft Graph rejected the message",
                code=f"graph_send_{response.status_code}",
                retryable=response.status_code >= 500 or response.status_code == 429,
                retry_after_seconds=_retry_after(response),
            )
        return SendResult(accepted=True, provider_status="accepted")


def _retry_after(response: httpx.Response) -> int | None:
    value = response.headers.get("Retry-After")
    return int(value) if value and value.isdigit() else None
