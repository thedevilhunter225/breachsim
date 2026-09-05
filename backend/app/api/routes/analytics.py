from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_role_names, require_roles
from app.db.session import get_db
from app.models.entities import Organization
from app.models.enums import ReportingIdentityMode, UserRole
from app.schemas.analytics import DashboardResponse, RiskIntelligenceResponse
from app.services.analytics import build_dashboard, build_risk_intelligence

router = APIRouter()


@router.get("/analytics/dashboard", response_model=DashboardResponse)
def dashboard(db: Annotated[Session, Depends(get_db)], user=Depends(require_roles(UserRole.ADMIN, UserRole.CAMPAIGN_MANAGER, UserRole.AUDITOR))):
    return build_dashboard(db, user.organization_id)


@router.get("/analytics/risk-distribution")
def risk_distribution(db: Annotated[Session, Depends(get_db)], user=Depends(require_roles(UserRole.ADMIN, UserRole.CAMPAIGN_MANAGER, UserRole.AUDITOR))):
    dashboard_data = build_dashboard(db, user.organization_id)
    return dashboard_data.risk_distribution


@router.get("/analytics/departments")
def department_insights(db: Annotated[Session, Depends(get_db)], user=Depends(require_roles(UserRole.ADMIN, UserRole.CAMPAIGN_MANAGER, UserRole.AUDITOR))):
    dashboard_data = build_dashboard(db, user.organization_id)
    return dashboard_data.vulnerable_departments


@router.get("/analytics/risk-intelligence", response_model=RiskIntelligenceResponse)
def risk_intelligence(db: Annotated[Session, Depends(get_db)], user=Depends(require_roles(UserRole.ADMIN, UserRole.CAMPAIGN_MANAGER, UserRole.AUDITOR))):
    organization = db.query(Organization).filter(Organization.id == user.organization_id).one()
    include_identities = (
        organization.reporting_identity_mode == ReportingIdentityMode.NAMED
        and UserRole.RISK_IDENTITY_VIEWER.value in get_role_names(user)
    )
    return build_risk_intelligence(db, user.organization_id, include_identities=include_identities)
