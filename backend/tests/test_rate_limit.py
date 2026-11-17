from __future__ import annotations

import asyncio

from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings
from app.core.rate_limit import RateLimitMiddleware


class FakePipeline:
    def __init__(self, current: int, ttl: int):
        self.result = [current, ttl]

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    def incr(self, _key):
        return self

    def ttl(self, _key):
        return self

    async def execute(self):
        return self.result


class FakeRedis:
    def __init__(self, current: int, ttl: int = 30, *, broken: bool = False):
        self.current = current
        self.ttl = ttl
        self.broken = broken
        self.expired = False

    def pipeline(self, **_kwargs):
        if self.broken:
            raise ConnectionError("redis unavailable")
        return FakePipeline(self.current, self.ttl)

    async def expire(self, _key, _seconds):
        self.expired = True


def login_request(path: str = "/api/v1/auth/login", method: str = "POST") -> Request:
    return Request(
        {
            "type": "http",
            "method": method,
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": [],
            "client": ("203.0.113.8", 40000),
            "server": ("breachsim.example.com", 443),
            "scheme": "https",
        }
    )


async def ok_response(_request):
    return Response("ok")


def test_rate_limit_sets_headers_and_expiry():
    middleware = RateLimitMiddleware(ok_response)
    middleware.enabled = True
    middleware.redis = FakeRedis(current=1, ttl=-1)

    response = asyncio.run(middleware.dispatch(login_request(), ok_response))

    assert response.status_code == 200
    assert response.headers["X-RateLimit-Limit"] == str(settings.login_rate_limit_count)
    assert middleware.redis.expired is True


def test_rate_limit_blocks_excess_and_fails_closed():
    middleware = RateLimitMiddleware(ok_response)
    middleware.enabled = True
    middleware.redis = FakeRedis(current=settings.login_rate_limit_count + 1)
    limited = asyncio.run(middleware.dispatch(login_request(), ok_response))
    assert limited.status_code == 429

    middleware.redis = FakeRedis(current=1, broken=True)
    unavailable = asyncio.run(middleware.dispatch(login_request(), ok_response))
    assert unavailable.status_code == 503


def test_throttling_can_be_switched_on_outside_production(monkeypatch):
    # The test settings are a development environment, where the limiter is off by default.
    assert RateLimitMiddleware(ok_response).enabled is False

    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    assert RateLimitMiddleware(ok_response).enabled is True

    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "rate_limit_enabled", False)
    assert RateLimitMiddleware(ok_response).enabled is True, "production cannot switch it off"


def test_mfa_setup_shares_the_sign_in_budget():
    """Both routes check a password, so neither may be an unthrottled way to guess one."""
    middleware = RateLimitMiddleware(ok_response)
    middleware.enabled = True
    setup = login_request("/api/v1/auth/mfa/setup")

    assert middleware._limit_for(setup).scope == middleware._limit_for(login_request()).scope == "login"
    assert middleware._identity(setup, "login") == middleware._identity(login_request(), "login")

    middleware.redis = FakeRedis(current=settings.login_rate_limit_count + 1)
    assert asyncio.run(middleware.dispatch(setup, ok_response)).status_code == 429
    # Reading pages is never throttled.
    assert middleware._limit_for(login_request("/api/v1/auth/me", method="GET")) is None
