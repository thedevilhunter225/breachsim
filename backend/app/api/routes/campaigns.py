from __future__ import annotations

from datetime import datetime, timezone
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload, selectinload

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.entities import Campaign, CampaignScenario, CampaignTarget, DeliveryAttempt, Employee, Scenario
from app.models.enums import CampaignStatus, UserRole
from app.schemas.campaigns import CampaignCreate, CampaignRead, CampaignUpdate, DeliveryAttemptRead
from app.services.audit import audit_log
from app.services.deletion import delete_campaign
from app.services.delivery import deliver_campaign, deliver_campaign_email, launch_campaign_sandbox

router = APIRouter()


def serialize_attempt(attempt: DeliveryAttempt) -> DeliveryAttemptRead:
    return DeliveryAttemptRead(
        id=str(attempt.id),
        campaign_id=str(attempt.campaign_id),
        employee_id=str(attempt.employee_id),
        channel=attempt.channel,
        status=attempt.status,
        sandbox_mode=attempt.sandbox_mode,
        preview_payload=attempt.preview_payload,
        delivered_at=attempt.delivered_at,
    )


def serialize_campaign(campaign: Campaign) -> CampaignRead:
    return CampaignRead(
        id=str(campaign.id),
        name=campaign.name,
        description=campaign.description,
        channel=campaign.channel,
        campaign_type=campaign.campaign_type,
        status=campaign.status,
        schedule_at=campaign.schedule_at,
        throttling_per_hour=campaign.throttling_per_hour,
        requires_second_approval=campaign.requires_second_approval,
        sandbox_mode=campaign.sandbox_mode,
        learning_objective=campaign.learning_objective,
        target_filters=campaign.target_filters,
        target_count=len(campaign.targets),
        scenario_count=len(campaign.scenario_links),
    )


@router.get("/campaigns", response_model=list[CampaignRead])
def list_campaigns(db: Annotated[Session, Depends(get_db)], user=Depends(get_current_user)):
    campaigns = (
        db.query(Campaign)
        .options(selectinload(Campaign.targets), selectinload(Campaign.scenario_links))
        .filter(Campaign.organization_id == user.organization_id)
        .order_by(Campaign.created_at.desc())
        .all()
    )
    return [serialize_campaign(campaign) for campaign in campaigns]


@router.post("/campaigns", response_model=CampaignRead, status_code=status.HTTP_201_CREATED)
def create_campaign(
    payload: CampaignCreate,
    db: Annotated[Session, Depends(get_db)],
    user=Depends(require_roles(UserRole.ADMIN, UserRole.CAMPAIGN_MANAGER)),
):
    campaign = Campaign(
        organization_id=user.organization_id,
        created_by_user_id=user.id,
        name=payload.name,
        description=payload.description,
        channel=payload.channel,
        campaign_type=payload.campaign_type,
        schedule_at=payload.schedule_at,
        throttling_per_hour=payload.throttling_per_hour,
        requires_second_approval=payload.requires_second_approval,
        sandbox_mode=payload.sandbox_mode,
        learning_objective=payload.learning_objective,
        target_filters=payload.target_filters,
        status=CampaignStatus.DRAFT,
    )
    db.add(campaign)
    db.flush()

    for employee_id in payload.target_employee_ids:
        employee = db.query(Employee).filter(Employee.id == employee_id, Employee.organization_id == user.organization_id).first()
        if employee:
            db.add(CampaignTarget(campaign_id=campaign.id, employee_id=employee.id, target_group_label="manual"))

    for scenario_id in payload.scenario_ids:
        scenario = db.query(Scenario).filter(Scenario.id == scenario_id, Scenario.organization_id == user.organization_id).first()
        if scenario:
            db.add(CampaignScenario(campaign_id=campaign.id, scenario_id=scenario.id))

    audit_log(db, organization_id=user.organization_id, user_id=user.id, action="campaign.create", resource_type="campaign", resource_id=str(campaign.id), details=payload.model_dump(mode="json"))
    db.commit()
    db.refresh(campaign)
    campaign = db.query(Campaign).options(selectinload(Campaign.targets), selectinload(Campaign.scenario_links)).filter(Campaign.id == campaign.id).first()
    return serialize_campaign(campaign)


@router.get("/campaigns/{campaign_id}", response_model=CampaignRead)
def get_campaign(campaign_id: uuid.UUID, db: Annotated[Session, Depends(get_db)], user=Depends(get_current_user)):
    campaign = db.query(Campaign).options(selectinload(Campaign.targets), selectinload(Campaign.scenario_links)).filter(Campaign.id == campaign_id, Campaign.organization_id == user.organization_id).first()
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    return serialize_campaign(campaign)


@router.patch("/campaigns/{campaign_id}", response_model=CampaignRead)
def update_campaign(
    campaign_id: uuid.UUID,
    payload: CampaignUpdate,
    db: Annotated[Session, Depends(get_db)],
    user=Depends(require_roles(UserRole.ADMIN, UserRole.CAMPAIGN_MANAGER)),
):
    campaign = db.query(Campaign).options(selectinload(Campaign.targets), selectinload(Campaign.scenario_links)).filter(Campaign.id == campaign_id, Campaign.organization_id == user.organization_id).first()
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    for key, value in payload.model_dump(exclude_none=True).items():
        setattr(campaign, key, value)
    audit_log(db, organization_id=user.organization_id, user_id=user.id, action="campaign.update", resource_type="campaign", resource_id=str(campaign.id), details=payload.model_dump(exclude_none=True, mode="json"))
    db.commit()
    db.refresh(campaign)
    return serialize_campaign(campaign)


@router.post("/campaigns/{campaign_id}/request-approval", response_model=CampaignRead)
def request_approval(campaign_id: uuid.UUID, db: Annotated[Session, Depends(get_db)], user=Depends(require_roles(UserRole.ADMIN, UserRole.CAMPAIGN_MANAGER))):
    campaign = db.query(Campaign).options(selectinload(Campaign.targets), selectinload(Campaign.scenario_links)).filter(Campaign.id == campaign_id, Campaign.organization_id == user.organization_id).first()
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    if not campaign.targets or not campaign.scenario_links:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Campaign requires at least one target and one scenario")
    campaign.status = CampaignStatus.PENDING_APPROVAL
    audit_log(db, organization_id=user.organization_id, user_id=user.id, action="campaign.request_approval", resource_type="campaign", resource_id=str(campaign.id))
    db.commit()
    return serialize_campaign(campaign)


@router.post("/campaigns/{campaign_id}/approve", response_model=CampaignRead)
def approve_campaign(campaign_id: uuid.UUID, db: Annotated[Session, Depends(get_db)], user=Depends(require_roles(UserRole.ADMIN))):
    campaign = db.query(Campaign).options(selectinload(Campaign.targets), selectinload(Campaign.scenario_links)).filter(Campaign.id == campaign_id, Campaign.organization_id == user.organization_id).first()
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    if any(link.scenario.status.value != "approved" for link in campaign.scenario_links if link.scenario):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="All linked scenarios must be approved")
    if campaign.requires_second_approval:
        if campaign.approved_by_user_id is None:
            campaign.approved_by_user_id = user.id
            audit_log(db, organization_id=user.organization_id, user_id=user.id, action="campaign.first_approval", resource_type="campaign", resource_id=str(campaign.id))
            db.commit()
            db.refresh(campaign)
            return serialize_campaign(campaign)
        if campaign.approved_by_user_id == user.id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Second approval must be from a different admin")
        campaign.second_approved_by_user_id = user.id
    else:
        campaign.approved_by_user_id = user.id
    campaign.status = CampaignStatus.APPROVED
    audit_log(db, organization_id=user.organization_id, user_id=user.id, action="campaign.approve", resource_type="campaign", resource_id=str(campaign.id))
    db.commit()
    db.refresh(campaign)
    return serialize_campaign(campaign)


@router.post("/campaigns/{campaign_id}/launch-sandbox", response_model=list[DeliveryAttemptRead])
def launch_sandbox(campaign_id: uuid.UUID, db: Annotated[Session, Depends(get_db)], user=Depends(require_roles(UserRole.ADMIN, UserRole.CAMPAIGN_MANAGER))):
    attempts = launch_campaign_sandbox(db, campaign_id=campaign_id, actor=user)
    return [serialize_attempt(attempt) for attempt in attempts]


@router.post("/campaigns/{campaign_id}/deliver", response_model=list[DeliveryAttemptRead])
def deliver(campaign_id: uuid.UUID, db: Annotated[Session, Depends(get_db)], user=Depends(require_roles(UserRole.ADMIN, UserRole.CAMPAIGN_MANAGER))):
    """Run a campaign for real on whichever channel it targets."""
    attempts = deliver_campaign(db, campaign_id=campaign_id, actor=user)
    return [serialize_attempt(attempt) for attempt in attempts]


@router.post("/campaigns/{campaign_id}/deliver-email", response_model=list[DeliveryAttemptRead])
def deliver_email(campaign_id: uuid.UUID, db: Annotated[Session, Depends(get_db)], user=Depends(require_roles(UserRole.ADMIN, UserRole.CAMPAIGN_MANAGER))):
    """Retained for existing integrations; prefer the channel-agnostic /deliver endpoint."""
    attempts = deliver_campaign_email(db, campaign_id=campaign_id, actor=user)
    return [serialize_attempt(attempt) for attempt in attempts]


@router.post("/campaigns/{campaign_id}/pause", response_model=CampaignRead)
def pause_campaign(campaign_id: uuid.UUID, db: Annotated[Session, Depends(get_db)], user=Depends(require_roles(UserRole.ADMIN, UserRole.CAMPAIGN_MANAGER))):
    campaign = db.query(Campaign).options(selectinload(Campaign.targets), selectinload(Campaign.scenario_links)).filter(Campaign.id == campaign_id, Campaign.organization_id == user.organization_id).first()
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    campaign.status = CampaignStatus.PAUSED
    audit_log(db, organization_id=user.organization_id, user_id=user.id, action="campaign.pause", resource_type="campaign", resource_id=str(campaign.id))
    db.commit()
    return serialize_campaign(campaign)


@router.delete("/campaigns/{campaign_id}")
def delete(
    campaign_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    purge_evidence: bool = False,
    user=Depends(require_roles(UserRole.ADMIN)),
):
    """Delete a campaign. Active campaigns must be paused; recorded evidence needs purge_evidence."""
    result = delete_campaign(
        db,
        organization_id=user.organization_id,
        campaign_id=campaign_id,
        actor=user,
        purge_evidence=purge_evidence,
    )
    return result.as_dict()


@router.get("/delivery-attempts", response_model=list[DeliveryAttemptRead])
def list_delivery_attempts(db: Annotated[Session, Depends(get_db)], user=Depends(get_current_user)):
    attempts = (
        db.query(DeliveryAttempt)
        .join(Campaign, DeliveryAttempt.campaign_id == Campaign.id)
        .filter(Campaign.organization_id == user.organization_id)
        .order_by(DeliveryAttempt.created_at.desc())
        .all()
    )
    return [serialize_attempt(attempt) for attempt in attempts]
