from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.constants.roles import CARRIER_WRITE_ROLES
from src.controllers import carrier_controller
from src.middlewares.rbac import Principal, require_permission, require_roles
from src.schemas.carrier import CarrierUpdateIn

router = APIRouter(prefix="/carriers", tags=["carriers"])


@router.get("")
def list_carriers(
    principal: Principal = Depends(require_permission("carrier:read")),
    db: Session = Depends(get_db),
) -> dict:
    return {"items": carrier_controller.list_carriers(db)}


@router.patch("/{carrier_id}")
def update_carrier(
    carrier_id: int,
    payload: CarrierUpdateIn,
    request: Request,
    principal: Principal = Depends(require_roles(*CARRIER_WRITE_ROLES)),
    db: Session = Depends(get_db),
) -> dict:
    return carrier_controller.update_carrier(
        db, carrier_id, payload.model_dump(exclude_none=True), principal.email, principal.role, request
    )
