import json
import logging
import re
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from redis import Redis
from sqlalchemy import text
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.routes import (
    analytics,
    audit,
    auth,
    campaigns,
    employee_portal,
    employees,
    enterprise,
    integrations,
    media,
    orgs,
    personas,
    platform,
    policies,
    provider_webhooks,
    public,
    scenarios,
    scim,
    sso,
    training,
    users,
)
from app.core.config import is_production_environment, secret_key_is_insecure, settings
from app.core.rate_limit import RateLimitMiddleware
from app.db.session import engine, init_db

logger = logging.getLogger("breachsim")
PUBLIC_TOKEN_PATH = re.compile(
    r"/(?:q|l|training|simulation|media|qr-assets)/[^/?]+",
    flags=re.IGNORECASE,
)


def _configure_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


@asynccontextmanager
async def lifespan(_: FastAPI):
    _configure_logging()
    if secret_key_is_insecure():
        # Loud in dev, fatal in production (enforced in get_settings). A default secret
        # lets anyone mint an admin token, which bypasses every RBAC check.
        logging.getLogger("uvicorn.error").warning(
            "SECURITY: SECRET_KEY is the shipped default or too short. JWTs can be forged. "
            "Set a strong unique SECRET_KEY before exposing this instance to anyone."
        )
    init_db()
    yield

app = FastAPI(
    title="BreachSim API",
    version="0.1.0",
    description="Phishing simulation and security awareness platform",
    lifespan=lifespan,
    docs_url="/docs" if settings.api_docs_enabled else None,
    redoc_url="/redoc" if settings.api_docs_enabled else None,
    openapi_url="/openapi.json" if settings.api_docs_enabled else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts)
app.add_middleware(RateLimitMiddleware)


@app.middleware("http")
async def request_security_and_logging(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("unhandled request error", extra={"request_id": request_id})
        raise

    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    if is_production_environment(settings.environment):
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"

    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    event = {
        "event": "http_request",
        "request_id": request_id,
        "method": request.method,
        "path": PUBLIC_TOKEN_PATH.sub(lambda match: match.group(0).rsplit("/", 1)[0] + "/[redacted]", request.url.path),
        "status": response.status_code,
        "duration_ms": elapsed_ms,
    }
    if settings.log_json:
        logger.info(json.dumps(event, separators=(",", ":")))
    else:
        logger.info("http_request %s", event)
    return response

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/live", include_in_schema=False)
def health_live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready", include_in_schema=False)
def health_ready():
    checks: dict[str, str] = {}
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "unavailable"

    if is_production_environment(settings.environment):
        redis = Redis.from_url(settings.redis_url, socket_connect_timeout=1, socket_timeout=1)
        try:
            redis.ping()
            checks["redis"] = "ok"
        except Exception:
            checks["redis"] = "unavailable"
        finally:
            redis.close()

    if any(value != "ok" for value in checks.values()):
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not_ready", "checks": checks},
        )
    return {"status": "ready", "checks": checks}


app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(orgs.router, prefix="/api/v1", tags=["orgs"])
app.include_router(enterprise.router, prefix="/api/v1", tags=["enterprise"])
app.include_router(platform.router, prefix="/api/v1/platform", tags=["platform"])
app.include_router(scim.router, prefix="/api/v1/scim/v2", tags=["scim"])
app.include_router(sso.router, prefix="/api/v1/auth", tags=["sso"])
app.include_router(integrations.router, prefix="/api/v1", tags=["integrations"])
app.include_router(employees.router, prefix="/api/v1", tags=["employees"])
app.include_router(policies.router, prefix="/api/v1", tags=["policies"])
app.include_router(personas.router, prefix="/api/v1", tags=["personas"])
app.include_router(media.router, prefix="/api/v1", tags=["media"])
app.include_router(scenarios.router, prefix="/api/v1", tags=["scenarios"])
app.include_router(campaigns.router, prefix="/api/v1", tags=["campaigns"])
app.include_router(training.router, prefix="/api/v1", tags=["training"])
app.include_router(users.router, prefix="/api/v1", tags=["users"])
app.include_router(analytics.router, prefix="/api/v1", tags=["analytics"])
app.include_router(audit.router, prefix="/api/v1", tags=["audit"])
app.include_router(employee_portal.router, prefix="/api/v1", tags=["employee-portal"])
app.include_router(public.router, prefix="/api/v1/public", tags=["public"])
# Azure Front Door sends public campaign entry and non-tracking QR asset paths
# directly to the API origin. The authenticated training UI remains on the
# frontend origin, while the API representation stays under /api/v1/public.
app.include_router(public.router, include_in_schema=False)
app.include_router(provider_webhooks.router, prefix="/api/v1", tags=["provider-reconciliation"])
