from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.controllers import waybill_controller
from src.middlewares.rbac import Principal, require_permission

router = APIRouter(prefix="/waybills", tags=["waybills"])


@router.get("")
def list_waybills(
    status: str | None = Query(default=None),
    carrier_code: str | None = Query(default=None),
    q: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=25, ge=1, le=100),
    principal: Principal = Depends(require_permission("waybill:read")),
    db: Session = Depends(get_db),
) -> dict:
    return waybill_controller.list_waybills(db, principal, status, carrier_code, q, page, size)


@router.get("/summary")
def summary(
    principal: Principal = Depends(require_permission("waybill:read")),
    db: Session = Depends(get_db),
) -> dict:
    return {"buckets": waybill_controller.buckets(db, principal)}


@router.get("/{waybill_id}")
def get_waybill(
    waybill_id: int,
    principal: Principal = Depends(require_permission("waybill:read")),
    db: Session = Depends(get_db),
) -> dict:
    return waybill_controller.get_waybill(db, waybill_id, principal)
