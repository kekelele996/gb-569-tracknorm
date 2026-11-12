"""承运商配置：读取、更新配额/频率、序列化。"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.models.carrier import Carrier
from src.models.waybill import Waybill
from src.utils.errors import AppError
from src.utils.timeutil import iso_utc


def serialize(carrier: Carrier) -> dict:
    return {
        "id": carrier.id,
        "code": carrier.code,
        "name": carrier.name,
        "status_code_system": carrier.status_code_system,
        "api_base": carrier.api_base,
        "daily_quota": carrier.daily_quota,
        "rate_limit_per_min": carrier.rate_limit_per_min,
        "avg_latency_ms": carrier.avg_latency_ms,
        "is_active": carrier.is_active,
        "note": carrier.note,
        "last_pull_at": iso_utc(carrier.last_pull_at),
        "last_pull_stats": carrier.last_pull_stats or {},
    }


def list_carriers(db: Session) -> list[dict]:
    counts = dict(
        db.execute(select(Waybill.carrier_id, func.count()).group_by(Waybill.carrier_id)).all()
    )
    carriers = db.scalars(select(Carrier).order_by(Carrier.id)).all()
    payload = []
    for carrier in carriers:
        item = serialize(carrier)
        item["waybill_count"] = int(counts.get(carrier.id, 0))
        payload.append(item)
    return payload


def get_carrier(db: Session, carrier_id: int) -> Carrier:
    carrier = db.get(Carrier, carrier_id)
    if carrier is None:
        raise AppError("NOT_FOUND", 404, detail=f"carrier {carrier_id}")
    return carrier


def update_carrier(db: Session, carrier_id: int, payload: dict) -> Carrier:
    carrier = get_carrier(db, carrier_id)
    for field in ("daily_quota", "rate_limit_per_min", "is_active", "note"):
        value = payload.get(field)
        if value is not None:
            setattr(carrier, field, value)
    db.flush()
    return carrier
