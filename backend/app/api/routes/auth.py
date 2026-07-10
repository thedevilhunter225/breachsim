from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.security import create_access_token
from app.db.session import get_db
from app.schemas.auth import LoginRequest, TokenResponse
from app.services.auth import authenticate_user, serialize_user

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Annotated[Session, Depends(get_db)]) -> TokenResponse:
    user = authenticate_user(db, payload.email, payload.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token(str(user.id))
    return TokenResponse(access_token=token, user=serialize_user(user))


@router.get("/me", response_model=TokenResponse)
def me(user=Depends(get_current_user)) -> TokenResponse:
    token = create_access_token(str(user.id))
    return TokenResponse(access_token=token, user=serialize_user(user))


@router.post("/logout")
def logout() -> dict[str, str]:
    return {"status": "ok"}
