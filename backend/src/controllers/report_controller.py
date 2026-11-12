"""报表控制器：数据质量、延迟说明 CSV、审计与拉取日志。"""
from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from src.middlewares.rbac import Principal
from src.services import audit_service, quality_service, report_service


def quality(db: Session) -> dict:
    return {"items": quality_service.carrier_quality(db)}


def delay_notices(db: Session, principal: Principal, request: Request) -> tuple[str, int]:
    content, rows = report_service.delay_notice_csv(db, principal)
    audit_service.record(
        db,
        actor_email=principal.email,
        actor_role=principal.role,
        action="report.export",
        entity="stagnation_alert",
        entity_id="delay_notices.csv",
        detail={"rows": rows, "scope": "own" if principal.role == "client" else "all"},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return content, rows


def audit_logs(db: Session, limit: int) -> dict:
    return report_service.audit_logs(db, limit)


def pull_logs(db: Session, limit: int) -> dict:
    return report_service.pull_logs(db, limit)
