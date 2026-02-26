from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.db import get_db
from src.core.security import get_current_user
from src.models.models import Notification, User
from src.schemas.schemas import NotificationOut

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get(
    "",
    response_model=list[NotificationOut],
    summary="List notifications",
    description="List notifications for the current user.",
    operation_id="notifications_list",
)
def list_notifications(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[NotificationOut]:
    stmt = select(Notification).where(Notification.user_id == user.id).order_by(Notification.created_at.desc())
    notifs = list(db.scalars(stmt).all())
    return [
        NotificationOut(
            id=n.id,
            type=n.type,
            title=n.title,
            body=n.body,
            data=n.data or {},
            created_at=n.created_at,
            read_at=n.read_at,
        )
        for n in notifs
    ]


@router.post(
    "/{notification_id}/read",
    response_model=NotificationOut,
    summary="Mark notification read",
    description="Mark a notification as read.",
    operation_id="notifications_mark_read",
)
def mark_read(
    notification_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> NotificationOut:
    n = db.scalar(select(Notification).where(Notification.id == notification_id))
    if not n or n.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")

    if n.read_at is None:
        n.read_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(n)

    return NotificationOut(
        id=n.id,
        type=n.type,
        title=n.title,
        body=n.body,
        data=n.data or {},
        created_at=n.created_at,
        read_at=n.read_at,
    )
