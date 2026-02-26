from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.audit import write_audit_log
from src.core.db import get_db
from src.core.security import create_access_token, get_current_user, verify_password
from src.models.models import Resident, User
from src.schemas.schemas import LoginRequest, MeResponse, TokenResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login",
    description="Authenticate with email/password and receive a JWT access token.",
    operation_id="auth_login",
)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == payload.email))
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token(subject=str(user.id))

    # Audit (best-effort, but keep as part of flow with flush)
    write_audit_log(
        db=db,
        actor_user_id=user.id,
        action="LOGIN",
        entity_type="users",
        entity_id=user.id,
        details={"email": user.email},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()
    logger.info("login_success user_id=%s email=%s", user.id, user.email)
    return TokenResponse(access_token=token)


@router.get(
    "/me",
    response_model=MeResponse,
    summary="Current user",
    description="Return the authenticated user's profile and roles.",
    operation_id="auth_me",
)
def me(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> MeResponse:
    resident = db.scalar(select(Resident).where(Resident.user_id == user.id))
    return MeResponse(
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        roles=[r.name for r in (user.roles or [])],
        resident_id=resident.id if resident else None,
    )
