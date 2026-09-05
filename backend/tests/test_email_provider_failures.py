from __future__ import annotations

import httpx
import pytest

from app.models.entities import EmailConnection
from app.models.enums import EmailProviderKind
from app.services.email_providers.base import EmailEnvelope, ProviderError
from app.services.email_providers.google_workspace import GoogleWorkspaceProvider
from app.services.email_providers.microsoft_graph import MicrosoftGraphProvider


def _envelope() -> EmailEnvelope:
    return EmailEnvelope(
        recipient="employee@example.com",
        sender_email="training@example.com",
        sender_name="Security Awareness",
        subject="Approved training notice",
        text_body="Training notice",
        html_body="<p>Training notice</p>",
        idempotency_key="attempt-12345678",
    )


def _connection(provider: EmailProviderKind) -> EmailConnection:
    return EmailConnection(
        provider=provider,
        sender_email="training@example.com",
        sender_name="Security Awareness",
        delegated_subject="training@example.com",
    )


@pytest.mark.parametrize(
    ("provider_class", "provider_kind", "status_code", "expected_retryable"),
    [
        (MicrosoftGraphProvider, EmailProviderKind.MICROSOFT_GRAPH, 401, False),
        (MicrosoftGraphProvider, EmailProviderKind.MICROSOFT_GRAPH, 403, False),
        (MicrosoftGraphProvider, EmailProviderKind.MICROSOFT_GRAPH, 429, True),
        (MicrosoftGraphProvider, EmailProviderKind.MICROSOFT_GRAPH, 503, True),
        (GoogleWorkspaceProvider, EmailProviderKind.GOOGLE_WORKSPACE, 401, False),
        (GoogleWorkspaceProvider, EmailProviderKind.GOOGLE_WORKSPACE, 429, True),
        (GoogleWorkspaceProvider, EmailProviderKind.GOOGLE_WORKSPACE, 503, True),
    ],
)
def test_provider_retry_classification(monkeypatch, provider_class, provider_kind, status_code, expected_retryable):
    provider = provider_class(_connection(provider_kind))
    monkeypatch.setattr(provider, "_access_token", lambda: "access-token")
    monkeypatch.setattr(
        httpx,
        "post",
        lambda *args, **kwargs: httpx.Response(
            status_code,
            headers={"Retry-After": "17"},
            json={"id": "gmail-id"},
            request=httpx.Request("POST", "https://provider.test/send"),
        ),
    )
    with pytest.raises(ProviderError) as exc:
        provider.send(_envelope())
    assert exc.value.retryable is expected_retryable
    assert exc.value.retry_after_seconds == 17
    assert exc.value.outcome_unknown is False


@pytest.mark.parametrize(
    ("provider_class", "provider_kind"),
    [
        (MicrosoftGraphProvider, EmailProviderKind.MICROSOFT_GRAPH),
        (GoogleWorkspaceProvider, EmailProviderKind.GOOGLE_WORKSPACE),
    ],
)
def test_submission_timeout_is_unknown_and_not_retried(monkeypatch, provider_class, provider_kind):
    provider = provider_class(_connection(provider_kind))
    monkeypatch.setattr(provider, "_access_token", lambda: "access-token")

    def timeout(*args, **kwargs):
        raise httpx.ReadTimeout("provider timed out", request=httpx.Request("POST", "https://provider.test/send"))

    monkeypatch.setattr(httpx, "post", timeout)
    with pytest.raises(ProviderError) as exc:
        provider.send(_envelope())
    assert exc.value.retryable is False
    assert exc.value.outcome_unknown is True
