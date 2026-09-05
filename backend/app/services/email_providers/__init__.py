from app.services.email_providers.base import EmailEnvelope, EmailProvider, ProviderError, SendResult
from app.services.email_providers.factory import provider_for_connection

__all__ = ["EmailEnvelope", "EmailProvider", "ProviderError", "SendResult", "provider_for_connection"]
