from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.audit import write_audit_log
from src.core.db import get_db
from src.core.security import get_current_resident, get_current_user, require_roles
from src.models.models import Resident, ResidentPrivacySettings, User
from src.schemas.schemas import ResidentCreate, ResidentOut, ResidentUpdate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/residents", tags=["residents"])


def _ensure_privacy_row(db: Session, resident: Resident) -> ResidentPrivacySettings:
    privacy = resident.privacy
    if not privacy:
        privacy = ResidentPrivacySettings(resident_id=resident.id)
        db.add(privacy)
        db.flush()
    return privacy


@router.post(
    "",
    response_model=ResidentOut,
    summary="Create resident (admin)",
    description="Create a resident profile. Admin-only.",
    operation_id="residents_create",
)
def create_resident(
    payload: ResidentCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles({"admin"})),
) -> ResidentOut:
    resident = Resident(
        user_id=payload.user_id,
        unit_number=payload.unit_number,
        building=payload.building,
        phone=payload.phone,
        email=payload.email,
        first_name=payload.first_name,
        last_name=payload.last_name,
        bio=payload.bio,
        profile_image_url=payload.profile_image_url,
        is_active=payload.is_active,
    )
    db.add(resident)
    db.flush()

    privacy = _ensure_privacy_row(db, resident)
    if payload.privacy:
        privacy.show_email = payload.privacy.show_email
        privacy.show_phone = payload.privacy.show_phone
        privacy.show_unit = payload.privacy.show_unit
        privacy.allow_messages = payload.privacy.allow_messages
        privacy.directory_visible = payload.privacy.directory_visible
        db.flush()

    write_audit_log(
        db=db,
        actor_user_id=actor.id,
        action="CREATE",
        entity_type="residents",
        entity_id=resident.id,
        details={"first_name": resident.first_name, "last_name": resident.last_name},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()
    db.refresh(resident)
    return _to_resident_out(resident)


@router.get(
    "/{resident_id}",
    response_model=ResidentOut,
    summary="Get resident (admin)",
    description="Get a resident profile including privacy settings. Admin-only.",
    operation_id="residents_get",
)
def get_resident(
    resident_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles({"admin"})),
) -> ResidentOut:
    resident = db.scalar(select(Resident).where(Resident.id == resident_id))
    if not resident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resident not found")
    _ensure_privacy_row(db, resident)
    return _to_resident_out(resident)


@router.patch(
    "/{resident_id}",
    response_model=ResidentOut,
    summary="Update resident (admin)",
    description="Update any resident profile. Admin-only.",
    operation_id="residents_update",
)
def update_resident(
    resident_id: uuid.UUID,
    payload: ResidentUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles({"admin"})),
) -> ResidentOut:
    resident = db.scalar(select(Resident).where(Resident.id == resident_id))
    if not resident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resident not found")

    _apply_resident_update(db, resident, payload)

    write_audit_log(
        db=db,
        actor_user_id=actor.id,
        action="UPDATE",
        entity_type="residents",
        entity_id=resident.id,
        details={"fields": list(payload.model_dump(exclude_none=True).keys())},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()
    db.refresh(resident)
    return _to_resident_out(resident)


@router.get(
    "/me/profile",
    response_model=ResidentOut,
    summary="Get my resident profile",
    description="Return the current user's resident profile, including privacy settings.",
    operation_id="residents_me_get",
)
def get_my_profile(db: Session = Depends(get_db), resident: Resident = Depends(get_current_resident)) -> ResidentOut:
    _ensure_privacy_row(db, resident)
    return _to_resident_out(resident)


@router.patch(
    "/me/profile",
    response_model=ResidentOut,
    summary="Update my resident profile",
    description="Update the current user's resident profile (including privacy settings).",
    operation_id="residents_me_update",
)
def update_my_profile(
    payload: ResidentUpdate,
    request: Request,
    db: Session = Depends(get_db),
    resident: Resident = Depends(get_current_resident),
    actor: User = Depends(get_current_user),
) -> ResidentOut:
    _apply_resident_update(db, resident, payload)

    write_audit_log(
        db=db,
        actor_user_id=actor.id,
        action="UPDATE_SELF",
        entity_type="residents",
        entity_id=resident.id,
        details={"fields": list(payload.model_dump(exclude_none=True).keys())},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()
    db.refresh(resident)
    return _to_resident_out(resident)


def _apply_resident_update(db: Session, resident: Resident, payload: ResidentUpdate) -> None:
    data = payload.model_dump(exclude_none=True)
    privacy_update = data.pop("privacy", None)

    for k, v in data.items():
        setattr(resident, k, v)

    if privacy_update is not None:
        privacy = _ensure_privacy_row(db, resident)
        # Overwrite specified privacy keys (payload already has defaults; treat as full replace)
        privacy.show_email = privacy_update.show_email
        privacy.show_phone = privacy_update.show_phone
        privacy.show_unit = privacy_update.show_unit
        privacy.allow_messages = privacy_update.allow_messages
        privacy.directory_visible = privacy_update.directory_visible


def _to_resident_out(resident: Resident) -> ResidentOut:
    privacy = resident.privacy
    privacy_out = None
    if privacy:
        from src.schemas.schemas import ResidentPrivacySettingsOut

        privacy_out = ResidentPrivacySettingsOut(
            resident_id=privacy.resident_id,
            show_email=privacy.show_email,
            show_phone=privacy.show_phone,
            show_unit=privacy.show_unit,
            allow_messages=privacy.allow_messages,
            directory_visible=privacy.directory_visible,
            updated_at=privacy.updated_at,
        )

    return ResidentOut(
        id=resident.id,
        user_id=resident.user_id,
        unit_number=resident.unit_number,
        building=resident.building,
        phone=resident.phone,
        email=resident.email,
        first_name=resident.first_name,
        last_name=resident.last_name,
        bio=resident.bio,
        profile_image_url=resident.profile_image_url,
        is_active=resident.is_active,
        created_at=resident.created_at,
        updated_at=resident.updated_at,
        privacy=privacy_out,
    )
