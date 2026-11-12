"""运单查询控制器（列表 / 状态分桶 / 详情）。"""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.middlewares.rbac import Principal
from src.services import waybill_service


def list_waybills(
    db: Session,
    principal: Principal,
    status: str | None,
    carrier_code: str | None,
    q: str | None,
    page: int,
    size: int,
) -> dict:
    payload = waybill_service.list_waybills(db, principal, status, carrier_code, q, page, size)
    payload["buckets"] = waybill_service.buckets(db, principal)
    return payload


def buckets(db: Session, principal: Principal) -> list[dict]:
    return waybill_service.buckets(db, principal)


def get_waybill(db: Session, waybill_id: int, principal: Principal) -> dict:
    return waybill_service.get_waybill(db, waybill_id, principal)
