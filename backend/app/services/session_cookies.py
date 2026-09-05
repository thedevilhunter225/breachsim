from __future__ import annotations

from fastapi import Response

from app.core.config import settings
from app.services.auth import SessionMaterial


def set_session_cookies(response: Response, session: SessionMaterial) -> None:
    cookie_options = {
        "secure": settings.session_cookie_secure,
        "samesite": "strict",
        "domain": settings.session_cookie_domain,
        "path": "/",
        "max_age": settings.session_absolute_hours * 3600,
    }
    response.set_cookie(
        settings.session_cookie_name,
        session.access_token,
        httponly=True,
        **cookie_options,
    )
    response.set_cookie(
        settings.csrf_cookie_name,
        session.csrf_token,
        httponly=False,
        **cookie_options,
    )


def clear_session_cookies(response: Response) -> None:
    response.delete_cookie(settings.session_cookie_name, path="/", domain=settings.session_cookie_domain)
    response.delete_cookie(settings.csrf_cookie_name, path="/", domain=settings.session_cookie_domain)
