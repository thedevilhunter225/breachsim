from __future__ import annotations

import hashlib
from dataclasses import dataclass

from fastapi import Request
from redis.asyncio import Redis
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response

from app.core.config import is_production_environment, settings


@dataclass(frozen=True)
class Limit:
    count: int
    window_seconds: int
    scope: str


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Redis-backed limits for authentication and unauthenticated mutation routes.

    Development and tests remain self-contained. Production fails closed if Redis is
    unavailable so brute-force protection never disappears silently.
    """

    def __init__(self, app):
        super().__init__(app)
        self.enabled = is_production_environment(settings.environment)
        self.redis = Redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )

    def _limit_for(self, request: Request) -> Limit | None:
        path = request.url.path
        if path == "/api/v1/auth/login" and request.method == "POST":
            return Limit(
                settings.login_rate_limit_count,
                settings.login_rate_limit_window_seconds,
                "login",
            )
        if path.startswith("/api/v1/public/") and request.method in {"POST", "PUT", "PATCH"}:
            return Limit(
                settings.public_rate_limit_count,
                settings.public_rate_limit_window_seconds,
                "public",
            )
        return None

    @staticmethod
    def _identity(request: Request, scope: str) -> str:
        client = request.client.host if request.client else "unknown"
        token_hint = request.url.path.rsplit("/", 2)[-2:] if scope == "public" else []
        raw = "|".join((scope, client, *token_hint))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        limit = self._limit_for(request) if self.enabled else None
        if not limit:
            return await call_next(request)

        key = f"breachsim:rate:{limit.scope}:{self._identity(request, limit.scope)}"
        try:
            async with self.redis.pipeline(transaction=True) as pipe:
                pipe.incr(key)
                pipe.ttl(key)
                current, ttl = await pipe.execute()
            if current == 1 or ttl < 0:
                await self.redis.expire(key, limit.window_seconds)
                ttl = limit.window_seconds
        except Exception:
            return JSONResponse(
                status_code=503,
                content={"detail": "Security rate-limit service is unavailable"},
                headers={"Retry-After": "5"},
            )

        if current > limit.count:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests"},
                headers={"Retry-After": str(max(int(ttl), 1))},
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit.count)
        response.headers["X-RateLimit-Remaining"] = str(max(limit.count - int(current), 0))
        return response
