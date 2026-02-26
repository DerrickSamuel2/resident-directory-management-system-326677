from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from src.core.db import get_db
from src.core.security import get_current_user
from src.models.models import Resident, ResidentPrivacySettings, User
from src.schemas.schemas import DirectoryResidentOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/directory", tags=["directory"])


@router.get(
    "",
    response_model=list[DirectoryResidentOut],
    summary="Browse directory",
    description="Browse/search the resident directory. Applies privacy settings to each profile.",
    operation_id="directory_list",
)
def list_directory(
    q: str | None = Query(None, description="Free-text search over name/building/unit"),
    building: str | None = Query(None, description="Filter by building"),
    include_inactive: bool = Query(False, description="Include inactive resident profiles (admin only)"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[DirectoryResidentOut]:
    is_admin = any(r.name == "admin" for r in (user.roles or []))

    stmt = (
        select(Resident, ResidentPrivacySettings)
        .join(ResidentPrivacySettings, ResidentPrivacySettings.resident_id == Resident.id, isouter=True)
    )

    conditions = []
    if not (include_inactive and is_admin):
        conditions.append(Resident.is_active.is_(True))
    if building:
        conditions.append(Resident.building == building)

    # Only show directory-visible to non-admins
    if not is_admin:
        conditions.append(or_(ResidentPrivacySettings.directory_visible.is_(True), ResidentPrivacySettings.directory_visible.is_(None)))

    if q:
        like = f"%{q.strip()}%"
        conditions.append(
            or_(
                Resident.first_name.ilike(like),
                Resident.last_name.ilike(like),
                Resident.building.ilike(like),
                Resident.unit_number.ilike(like),
            )
        )

    if conditions:
        stmt = stmt.where(and_(*conditions))

    stmt = stmt.order_by(Resident.last_name.asc(), Resident.first_name.asc())

    rows = db.execute(stmt).all()
    results: list[DirectoryResidentOut] = []
    for resident, privacy in rows:
        results.append(_project_directory_view(resident, privacy))

    logger.info("directory_list count=%s q=%s building=%s is_admin=%s", len(results), q, building, is_admin)
    return results


def _project_directory_view(resident: Resident, privacy: ResidentPrivacySettings | None) -> DirectoryResidentOut:
    # Defaults if no privacy row exists yet
    show_email = bool(privacy.show_email) if privacy else False
    show_phone = bool(privacy.show_phone) if privacy else False
    show_unit = bool(privacy.show_unit) if privacy else True
    allow_messages = bool(privacy.allow_messages) if privacy else True

    return DirectoryResidentOut(
        id=resident.id,
        first_name=resident.first_name,
        last_name=resident.last_name,
        building=resident.building,
        unit_number=resident.unit_number if show_unit else None,
        bio=resident.bio,
        profile_image_url=resident.profile_image_url,
        email=resident.email if show_email else None,
        phone=resident.phone if show_phone else None,
        allow_messages=allow_messages,
    )
