from __future__ import annotations

from app.models.entities import EmailConnection
from app.models.enums import EmailProviderKind
from app.services.email_providers.base import EmailProvider
from app.services.email_providers.google_workspace import GoogleWorkspaceProvider
from app.services.email_providers.microsoft_graph import MicrosoftGraphProvider


def provider_for_connection(connection: EmailConnection) -> EmailProvider:
    if connection.provider == EmailProviderKind.MICROSOFT_GRAPH:
        return MicrosoftGraphProvider(connection)
    if connection.provider == EmailProviderKind.GOOGLE_WORKSPACE:
        return GoogleWorkspaceProvider(connection)
    raise ValueError(f"Unsupported enterprise email provider: {connection.provider.value}")
