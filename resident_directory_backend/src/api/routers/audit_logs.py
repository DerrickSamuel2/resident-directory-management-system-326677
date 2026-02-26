from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.db import get_db
from src.core.security import require_roles
from src.models.models import AuditLog, User
from src.schemas.schemas import AuditLogOut

router = APIRouter(prefix="/audit-logs", tags=["audit"])


@router.get(
    "",
    response_model=list[AuditLogOut],
    summary="List audit logs (admin)",
    description="List audit logs. Admin-only.",
    operation_id="audit_list",
)
def list_audit_logs(
    limit: int = Query(50, ge=1, le=500, description="Max number of records to return"),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles({"admin"})),
) -> list[AuditLogOut]:
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
    logs = list(db.scalars(stmt).all())
    return [
        AuditLogOut(
            id=l.id,
            actor_user_id=l.actor_user_id,
            action=l.action,
            entity_type=l.entity_type,
            entity_id=l.entity_id,
            details=l.details or {},
            ip_address=str(l.ip_address) if l.ip_address else None,
            user_agent=l.user_agent,
            created_at=l.created_at,
        )
        for l in logs
    ]
