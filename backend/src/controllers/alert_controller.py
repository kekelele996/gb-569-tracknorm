"""停滞预警控制器。"""
from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from src.middlewares.rbac import Principal
from src.services import alert_service


def list_alerts(db: Session, principal: Principal, status: str | None, severity: str | None) -> dict:
    return alert_service.list_alerts(db, principal, status, severity)


def summary(db: Session, principal: Principal) -> dict:
    return alert_service.summary(db, principal)


def claim(db: Session, alert_id: int, principal: Principal, note: str | None, request: Request) -> dict:
    payload = alert_service.claim(
        db, alert_id, principal, note, ip=request.client.host if request.client else None
    )
    db.commit()
    return payload


def dispose(
    db: Session,
    alert_id: int,
    principal: Principal,
    disposition: str,
    note: str | None,
    request: Request,
) -> dict:
    payload = alert_service.dispose(
        db, alert_id, principal, disposition, note, ip=request.client.host if request.client else None
    )
    db.commit()
    return payload
