"""审计日志：领域层记录 + 查询。"""
from __future__ import annotations

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from src.constants.log_templates import ACTIONS
from src.models.audit import AuditLog
from src.utils.timeutil import iso_utc


def record(
    db: Session,
    actor_email: str,
    actor_role: str,
    action: str,
    entity: str,
    entity_id: str | int | None = None,
    detail: dict | None = None,
    layer: str = "domain",
    ip: str | None = None,
    seed_key: str | None = None,
) -> AuditLog:
    log = AuditLog(
        actor_email=actor_email,
        actor_role=actor_role,
        action=action,
        entity=entity,
        entity_id=str(entity_id) if entity_id is not None else None,
        detail=detail or {},
        layer=layer,
        ip=ip,
        seed_key=seed_key,
    )
    db.add(log)
    return log


def serialize(log: AuditLog) -> dict:
    return {
        "id": log.id,
        "actor_email": log.actor_email,
        "actor_role": log.actor_role,
        "action": log.action,
        "action_label": ACTIONS.get(log.action, log.action),
        "entity": log.entity,
        "entity_id": log.entity_id,
        "detail": log.detail,
        "layer": log.layer,
        "created_at": iso_utc(log.created_at),
    }


def list_logs(db: Session, limit: int = 60, actions: tuple[str, ...] | None = None) -> dict:
    stmt = select(AuditLog)
    if actions:
        stmt = stmt.where(AuditLog.action.in_(list(actions)))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(desc(AuditLog.id)).limit(limit)).all()
    return {"items": [serialize(row) for row in rows], "total": total}
