from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.constants.roles import MAPPING_WRITE_ROLES
from src.controllers import mapping_controller
from src.middlewares.rbac import Principal, require_permission, require_roles
from src.schemas.mapping import ActivateVersionIn, CreateVersionIn

router = APIRouter(prefix="/mappings", tags=["mappings"])


@router.get("/versions")
def list_versions(
    principal: Principal = Depends(require_permission("mapping:read")),
    db: Session = Depends(get_db),
) -> dict:
    return mapping_controller.list_versions(db)


@router.get("/evaluate")
def evaluate(
    version: int | None = Query(default=None, ge=1, le=99),
    principal: Principal = Depends(require_permission("mapping:read")),
    db: Session = Depends(get_db),
) -> dict:
    return mapping_controller.evaluate(db, version)


@router.post("/versions")
def create_version(
    payload: CreateVersionIn,
    request: Request,
    principal: Principal = Depends(require_roles(*MAPPING_WRITE_ROLES)),
    db: Session = Depends(get_db),
) -> dict:
    return mapping_controller.create_version(db, payload.base_version, payload.note, principal, request)


@router.post("/activate")
def activate(
    payload: ActivateVersionIn,
    request: Request,
    principal: Principal = Depends(require_roles(*MAPPING_WRITE_ROLES)),
    db: Session = Depends(get_db),
) -> dict:
    return mapping_controller.activate(db, payload.version, principal, request)


@router.get("")
def list_rules(
    version: int | None = Query(default=None, ge=1, le=99),
    principal: Principal = Depends(require_permission("mapping:read")),
    db: Session = Depends(get_db),
) -> dict:
    return mapping_controller.list_rules(db, version)
