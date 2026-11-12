from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.constants.roles import ALERT_HANDLE_ROLES
from src.controllers import alert_controller
from src.middlewares.rbac import Principal, require_permission, require_roles
from src.schemas.alert import ClaimIn, DisposeIn

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("")
def list_alerts(
    status: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    principal: Principal = Depends(require_permission("alert:read")),
    db: Session = Depends(get_db),
) -> dict:
    return alert_controller.list_alerts(db, principal, status, severity)


@router.get("/summary")
def summary(
    principal: Principal = Depends(require_permission("alert:read")),
    db: Session = Depends(get_db),
) -> dict:
    return alert_controller.summary(db, principal)


@router.post("/{alert_id}/claim")
def claim(
    alert_id: int,
    payload: ClaimIn,
    request: Request,
    principal: Principal = Depends(require_roles(*ALERT_HANDLE_ROLES)),
    db: Session = Depends(get_db),
) -> dict:
    return alert_controller.claim(db, alert_id, principal, payload.note, request)


@router.post("/{alert_id}/dispose")
def dispose(
    alert_id: int,
    payload: DisposeIn,
    request: Request,
    principal: Principal = Depends(require_roles(*ALERT_HANDLE_ROLES)),
    db: Session = Depends(get_db),
) -> dict:
    return alert_controller.dispose(db, alert_id, principal, payload.disposition, payload.note, request)
