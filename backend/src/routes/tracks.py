from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.constants.roles import TRACK_RUN_ROLES
from src.controllers import track_controller, waybill_controller
from src.middlewares.rbac import Principal, require_permission, require_roles
from src.schemas.trace import NormalizeIn, PullIn

router = APIRouter(prefix="/tracks", tags=["tracks"])


@router.post("/pull")
def pull(
    payload: PullIn,
    request: Request,
    principal: Principal = Depends(require_roles(*TRACK_RUN_ROLES)),
    db: Session = Depends(get_db),
) -> dict:
    return track_controller.pull(db, principal, request, payload.carrier_codes, payload.force)


@router.post("/normalize")
def normalize(
    payload: NormalizeIn,
    request: Request,
    principal: Principal = Depends(require_roles(*TRACK_RUN_ROLES)),
    db: Session = Depends(get_db),
) -> dict:
    return track_controller.normalize(db, principal, request, payload.version)


@router.get("/last-runs")
def last_runs(
    principal: Principal = Depends(require_permission("track:read")),
    db: Session = Depends(get_db),
) -> dict:
    return track_controller.last_runs(db)


@router.get("/{waybill_id}")
def get_track(
    waybill_id: int,
    principal: Principal = Depends(require_permission("track:read")),
    db: Session = Depends(get_db),
) -> dict:
    return waybill_controller.get_waybill(db, waybill_id, principal)
