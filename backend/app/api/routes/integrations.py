from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.entities import Organization
from app.models.enums import UserRole
from app.schemas.integrations import EmailIntegrationRead, EmailIntegrationUpdate
from app.services.audit import audit_log
from app.services.email_integration import serialize_email_integration, update_email_integration

router = APIRouter()


@router.get("/integrations/email", response_model=EmailIntegrationRead)
def get_email_integration(db: Annotated[Session, Depends(get_db)], user=Depends(require_roles(UserRole.ADMIN, UserRole.CAMPAIGN_MANAGER))):
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    return serialize_email_integration(org)


@router.put("/integrations/email", response_model=EmailIntegrationRead)
def put_email_integration(
    payload: EmailIntegrationUpdate,
    db: Annotated[Session, Depends(get_db)],
    user=Depends(require_roles(UserRole.ADMIN)),
):
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    update_email_integration(org, payload)
    audit_log(
        db,
        organization_id=user.organization_id,
        user_id=user.id,
        action="integration.email.update",
        resource_type="organization",
        resource_id=str(org.id),
        details={"email_provider_enabled": org.email_provider_enabled, "email_provider_mode": org.email_provider_mode},
    )
    db.commit()
    db.refresh(org)
    return serialize_email_integration(org)
