from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.models.entities import EmailConnection


@dataclass(frozen=True)
class EmailEnvelope:
    recipient: str
    sender_email: str
    sender_name: str
    subject: str
    text_body: str
    html_body: str
    idempotency_key: str
    headers: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class SendResult:
    accepted: bool
    provider_message_id: str | None = None
    provider_status: str = "accepted"


class ProviderError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        code: str,
        retryable: bool,
        retry_after_seconds: int | None = None,
        outcome_unknown: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable
        self.retry_after_seconds = retry_after_seconds
        self.outcome_unknown = outcome_unknown


class EmailProvider(ABC):
    def __init__(self, connection: EmailConnection) -> None:
        self.connection = connection

    @abstractmethod
    def health_check(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def send(self, envelope: EmailEnvelope) -> SendResult:
        raise NotImplementedError

    def revoke(self) -> None:
        return None
