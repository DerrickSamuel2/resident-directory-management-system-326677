from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from src.core.audit import write_audit_log
from src.core.db import get_db
from src.core.security import get_current_user
from src.models.models import Message, Notification, Resident, ResidentPrivacySettings, User
from src.schemas.schemas import MessageCreate, MessageOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/messages", tags=["messages"])


@router.post(
    "",
    response_model=MessageOut,
    summary="Send message",
    description="Send a 1:1 message to another user (if recipient allows messages).",
    operation_id="messages_send",
)
def send_message(
    payload: MessageCreate,
    request: Request,
    db: Session = Depends(get_db),
    sender: User = Depends(get_current_user),
) -> MessageOut:
    if payload.recipient_user_id == sender.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot message yourself")

    recipient = db.scalar(select(User).where(User.id == payload.recipient_user_id))
    if not recipient or not recipient.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipient not found")

    # Enforce recipient privacy (allow_messages)
    recipient_resident = db.scalar(select(Resident).where(Resident.user_id == recipient.id))
    if recipient_resident:
        privacy = db.scalar(
            select(ResidentPrivacySettings).where(ResidentPrivacySettings.resident_id == recipient_resident.id)
        )
        if privacy and not privacy.allow_messages:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Recipient does not allow messages")

    msg = Message(
        sender_user_id=sender.id,
        recipient_user_id=payload.recipient_user_id,
        subject=payload.subject,
        body=payload.body,
    )
    db.add(msg)
    db.flush()

    notif = Notification(
        user_id=payload.recipient_user_id,
        type="message",
        title="New message",
        body=f"You have a new message from {sender.full_name or sender.email}.",
        data={"from_user_id": str(sender.id), "message_id": str(msg.id)},
    )
    db.add(notif)

    write_audit_log(
        db=db,
        actor_user_id=sender.id,
        action="SEND_MESSAGE",
        entity_type="messages",
        entity_id=msg.id,
        details={"recipient_user_id": str(payload.recipient_user_id)},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    db.commit()
    db.refresh(msg)

    logger.info("message_sent message_id=%s sender=%s recipient=%s", msg.id, sender.id, payload.recipient_user_id)
    return _to_message_out(msg)


@router.get(
    "/inbox",
    response_model=list[MessageOut],
    summary="Inbox",
    description="List received messages for the current user.",
    operation_id="messages_inbox",
)
def inbox(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[MessageOut]:
    stmt = (
        select(Message)
        .where(
            and_(
                Message.recipient_user_id == user.id,
                Message.is_deleted_by_recipient.is_(False),
            )
        )
        .order_by(Message.sent_at.desc())
    )
    msgs = list(db.scalars(stmt).all())
    return [_to_message_out(m) for m in msgs]


@router.get(
    "/sent",
    response_model=list[MessageOut],
    summary="Sent messages",
    description="List sent messages for the current user.",
    operation_id="messages_sent",
)
def sent(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[MessageOut]:
    stmt = (
        select(Message)
        .where(
            and_(
                Message.sender_user_id == user.id,
                Message.is_deleted_by_sender.is_(False),
            )
        )
        .order_by(Message.sent_at.desc())
    )
    msgs = list(db.scalars(stmt).all())
    return [_to_message_out(m) for m in msgs]


@router.post(
    "/{message_id}/read",
    response_model=MessageOut,
    summary="Mark as read",
    description="Mark a message as read (recipient only).",
    operation_id="messages_mark_read",
)
def mark_read(
    message_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MessageOut:
    msg = db.scalar(select(Message).where(Message.id == message_id))
    if not msg or msg.recipient_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

    if msg.read_at is None:
        from datetime import datetime, timezone

        msg.read_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(msg)

    return _to_message_out(msg)


def _to_message_out(msg: Message) -> MessageOut:
    return MessageOut(
        id=msg.id,
        sender_user_id=msg.sender_user_id,
        recipient_user_id=msg.recipient_user_id,
        subject=msg.subject,
        body=msg.body,
        sent_at=msg.sent_at,
        read_at=msg.read_at,
    )
