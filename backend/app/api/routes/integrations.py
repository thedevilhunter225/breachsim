from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.config import is_production_environment, settings
from app.db.session import get_db
from app.models.entities import ImpersonationPersona, Organization
from app.models.enums import PersonaStatus, UserRole
from app.schemas.integrations import (
    EmailIntegrationRead,
    EmailIntegrationUpdate,
    ImpersonationSettingsRead,
    ImpersonationSettingsUpdate,
    SmsIntegrationRead,
    SmsIntegrationUpdate,
)
from app.services.audit import audit_log
from app.services.email_integration import serialize_email_integration, update_email_integration
from app.services.media import video_provider_status, voice_provider_status
from app.services.sms_integration import serialize_sms_integration, update_sms_integration

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
    if is_production_environment(settings.environment) and payload.email_provider_enabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="SMTP is local/demo only. Configure Microsoft Graph or Google Workspace for enterprise campaigns.",
        )
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


@router.get("/integrations/sms", response_model=SmsIntegrationRead)
def get_sms_integration(
    db: Annotated[Session, Depends(get_db)],
    user=Depends(require_roles(UserRole.ADMIN, UserRole.CAMPAIGN_MANAGER)),
):
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    return serialize_sms_integration(org)


@router.put("/integrations/sms", response_model=SmsIntegrationRead)
def put_sms_integration(
    payload: SmsIntegrationUpdate,
    db: Annotated[Session, Depends(get_db)],
    user=Depends(require_roles(UserRole.ADMIN)),
):
    if is_production_environment(settings.environment) and payload.sms_provider_enabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="SMS is disabled for the initial production launch.",
        )
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    update_sms_integration(org, payload)
    audit_log(
        db,
        organization_id=user.organization_id,
        user_id=user.id,
        action="integration.sms.update",
        resource_type="organization",
        resource_id=str(org.id),
        details={
            "sms_provider_enabled": org.sms_provider_enabled,
            "sms_provider_mode": org.sms_provider_mode,
            "allowlist_size": len(org.sms_recipient_allowlist or []),
        },
    )
    db.commit()
    db.refresh(org)
    return serialize_sms_integration(org)


def _serialize_impersonation(db: Session, org: Organization) -> ImpersonationSettingsRead:
    approved = (
        db.query(ImpersonationPersona)
        .filter(
            ImpersonationPersona.organization_id == org.id,
            ImpersonationPersona.status == PersonaStatus.APPROVED,
        )
        .count()
    )
    voice_status = voice_provider_status()
    video_status = video_provider_status()
    return ImpersonationSettingsRead(
        impersonation_enabled=org.impersonation_enabled,
        impersonation_disclosure_text=org.impersonation_disclosure_text,
        approved_persona_count=approved,
        voice_provider_enabled=org.voice_provider_enabled,
        voice_provider_mode=org.voice_provider_mode,
        voice_clone_provider=voice_status["provider"],
        voice_clone_configured=voice_status["configured"],
        video_clone_provider=video_status["provider"],
        video_clone_configured=video_status["configured"],
    )


@router.get("/integrations/impersonation", response_model=ImpersonationSettingsRead)
def get_impersonation_settings(
    db: Annotated[Session, Depends(get_db)],
    user=Depends(require_roles(UserRole.ADMIN, UserRole.CAMPAIGN_MANAGER)),
):
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    return _serialize_impersonation(db, org)


@router.put("/integrations/impersonation", response_model=ImpersonationSettingsRead)
def put_impersonation_settings(
    payload: ImpersonationSettingsUpdate,
    db: Annotated[Session, Depends(get_db)],
    user=Depends(require_roles(UserRole.ADMIN)),
):
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    org.impersonation_enabled = payload.impersonation_enabled
    if payload.impersonation_disclosure_text:
        org.impersonation_disclosure_text = payload.impersonation_disclosure_text
    org.voice_provider_enabled = payload.voice_provider_enabled
    org.voice_provider_mode = payload.voice_provider_mode
    audit_log(
        db,
        organization_id=user.organization_id,
        user_id=user.id,
        action="integration.impersonation.update",
        resource_type="organization",
        resource_id=str(org.id),
        details={
            "impersonation_enabled": org.impersonation_enabled,
            "voice_provider_mode": org.voice_provider_mode,
        },
    )
    db.commit()
    db.refresh(org)
    return _serialize_impersonation(db, org)
