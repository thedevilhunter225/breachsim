from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.entities import ImpersonationPersona
from app.models.enums import UserRole
from app.schemas.personas import PersonaCreate, PersonaRead, PersonaRevokeRequest
from app.services.deletion import delete_persona
from app.services.personas import (
    approve_persona,
    create_persona,
    get_persona,
    list_personas,
    revoke_persona,
)

router = APIRouter()


def serialize(persona: ImpersonationPersona) -> PersonaRead:
    read = PersonaRead.model_validate(persona)
    read.usable = persona.is_usable()
    return read


@router.get("/personas", response_model=list[PersonaRead])
def list_all(db: Annotated[Session, Depends(get_db)], user=Depends(get_current_user)):
    return [serialize(persona) for persona in list_personas(db, user.organization_id)]


@router.post("/personas", response_model=PersonaRead, status_code=status.HTTP_201_CREATED)
def create(
    payload: PersonaCreate,
    db: Annotated[Session, Depends(get_db)],
    user=Depends(require_roles(UserRole.ADMIN)),
):
    return serialize(create_persona(db, actor=user, payload=payload))


@router.get("/personas/{persona_id}", response_model=PersonaRead)
def read_one(persona_id: uuid.UUID, db: Annotated[Session, Depends(get_db)], user=Depends(get_current_user)):
    return serialize(get_persona(db, user.organization_id, persona_id))


@router.post("/personas/{persona_id}/approve", response_model=PersonaRead)
def approve(
    persona_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    user=Depends(require_roles(UserRole.ADMIN)),
):
    persona = get_persona(db, user.organization_id, persona_id)
    return serialize(approve_persona(db, persona=persona, actor=user))


@router.delete("/personas/{persona_id}")
def delete(
    persona_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    user=Depends(require_roles(UserRole.ADMIN)),
):
    """Delete an unused persona. One with scenario history must be revoked instead."""
    result = delete_persona(db, organization_id=user.organization_id, persona_id=persona_id, actor=user)
    return result.as_dict()


@router.post("/personas/{persona_id}/revoke", response_model=PersonaRead)
def revoke(
    persona_id: uuid.UUID,
    payload: PersonaRevokeRequest,
    db: Annotated[Session, Depends(get_db)],
    user=Depends(require_roles(UserRole.ADMIN)),
):
    persona = get_persona(db, user.organization_id, persona_id)
    return serialize(revoke_persona(db, persona=persona, actor=user, reason=payload.reason))
