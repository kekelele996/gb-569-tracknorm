from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.constants.roles import AUDIT_READ_ROLES, QUALITY_READ_ROLES
from src.controllers import report_controller
from src.middlewares.rbac import Principal, require_permission, require_roles

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/quality")
def quality(
    principal: Principal = Depends(require_roles(*QUALITY_READ_ROLES)),
    db: Session = Depends(get_db),
) -> dict:
    return report_controller.quality(db)


@router.get("/delay-notices.csv")
def delay_notices(
    request: Request,
    principal: Principal = Depends(require_permission("report:export")),
    db: Session = Depends(get_db),
) -> Response:
    content, rows = report_controller.delay_notices(db, principal, request)
    headers = {
        "Content-Disposition": 'attachment; filename="tracknorm-delay-notices.csv"',
        "X-Row-Count": str(rows),
    }
    return Response(content=content, media_type="text/csv; charset=utf-8", headers=headers)


@router.get("/audit")
def audit(
    limit: int = Query(default=60, ge=1, le=200),
    principal: Principal = Depends(require_roles(*AUDIT_READ_ROLES)),
    db: Session = Depends(get_db),
) -> dict:
    return report_controller.audit_logs(db, limit)


@router.get("/pull-logs")
def pull_logs(
    limit: int = Query(default=20, ge=1, le=100),
    principal: Principal = Depends(require_roles(*AUDIT_READ_ROLES)),
    db: Session = Depends(get_db),
) -> dict:
    return report_controller.pull_logs(db, limit)
