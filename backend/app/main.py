import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    analytics,
    audit,
    auth,
    campaigns,
    employee_portal,
    employees,
    integrations,
    media,
    orgs,
    personas,
    policies,
    public,
    scenarios,
    training,
)
from app.core.config import secret_key_is_insecure, settings
from app.db.session import init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
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
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(orgs.router, prefix="/api/v1", tags=["orgs"])
app.include_router(integrations.router, prefix="/api/v1", tags=["integrations"])
app.include_router(employees.router, prefix="/api/v1", tags=["employees"])
app.include_router(policies.router, prefix="/api/v1", tags=["policies"])
app.include_router(personas.router, prefix="/api/v1", tags=["personas"])
app.include_router(media.router, prefix="/api/v1", tags=["media"])
app.include_router(scenarios.router, prefix="/api/v1", tags=["scenarios"])
app.include_router(campaigns.router, prefix="/api/v1", tags=["campaigns"])
app.include_router(training.router, prefix="/api/v1", tags=["training"])
app.include_router(analytics.router, prefix="/api/v1", tags=["analytics"])
app.include_router(audit.router, prefix="/api/v1", tags=["audit"])
app.include_router(employee_portal.router, prefix="/api/v1", tags=["employee-portal"])
app.include_router(public.router, prefix="/api/v1/public", tags=["public"])
