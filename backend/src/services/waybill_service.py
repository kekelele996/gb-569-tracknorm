"""运单查询：列表/状态分桶/详情（含原始事件与归一轨迹），client 角色只看自己的单。"""
from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from src.constants.enums import (
    NORMALIZED_STATUS_LABELS,
    NormalizedStatus,
    SERVICE_LEVEL_LABELS,
)
from src.middlewares.rbac import Principal
from src.models.carrier import Carrier
from src.models.normalized_track import NormalizedTrack
from src.models.stagnation_alert import StagnationAlert
from src.models.trace_event import TraceEvent
from src.models.waybill import Waybill
from src.utils.errors import AppError
from src.utils.geo import lane_key
from src.utils.timeutil import iso_utc

BUCKET_ORDER = [
    NormalizedStatus.CREATED.value,
    NormalizedStatus.COLLECTED.value,
    NormalizedStatus.IN_TRANSIT.value,
    NormalizedStatus.ARRIVED_HUB.value,
    NormalizedStatus.OUT_FOR_DELIVERY.value,
    NormalizedStatus.DELIVERED.value,
    NormalizedStatus.EXCEPTION.value,
    NormalizedStatus.RETURNING.value,
]


def _scope_to_client(stmt, principal: Principal):
    if principal.role == "client":
        return stmt.where(Waybill.client_account == principal.email)
    return stmt


def serialize_waybill(waybill: Waybill, carrier: Carrier, track: NormalizedTrack | None) -> dict:
    return {
        "id": waybill.id,
        "waybill_no": waybill.waybill_no,
        "carrier_id": waybill.carrier_id,
        "carrier_code": carrier.code,
        "carrier_name": carrier.name,
        "client_account": waybill.client_account,
        "client_ref": waybill.client_ref,
        "lane": lane_key(waybill.origin_region, waybill.dest_region),
        "origin_region": waybill.origin_region,
        "dest_region": waybill.dest_region,
        "origin_city": waybill.origin_city,
        "dest_city": waybill.dest_city,
        "service_level": waybill.service_level,
        "service_level_label": SERVICE_LEVEL_LABELS.get(waybill.service_level, waybill.service_level),
        "weight_kg": waybill.weight_kg,
        "current_status": waybill.current_status,
        "current_status_label": NORMALIZED_STATUS_LABELS.get(waybill.current_status, waybill.current_status),
        "trace_stage": waybill.trace_stage,
        "trace_stage_label": NORMALIZED_STATUS_LABELS.get(waybill.trace_stage, waybill.trace_stage),
        "promised_delivery_at": iso_utc(waybill.promised_delivery_at),
        "collected_at": iso_utc(waybill.collected_at),
        "last_event_at": iso_utc(waybill.last_event_at),
        "coverage": track.coverage if track else 0.0,
        "conflict_count": track.conflict_count if track else 0,
        "mapping_version": track.mapping_version if track else None,
        "event_count": track.event_count if track else 0,
    }


def carrier_options(db: Session, principal: Principal) -> list[dict]:
    """筛选下拉：只列出当前角色可见运单涉及的承运商（client 不会看到别家）。"""
    stmt = (
        select(Carrier.code, Carrier.name)
        .join(Waybill, Waybill.carrier_id == Carrier.id)
        .distinct()
        .order_by(Carrier.code)
    )
    stmt = _scope_to_client(stmt, principal)
    return [{"code": code, "name": name} for code, name in db.execute(stmt).all()]


def buckets(db: Session, principal: Principal) -> list[dict]:
    stmt = _scope_to_client(
        select(Waybill.current_status, func.count()).select_from(Waybill).group_by(Waybill.current_status),
        principal,
    )
    counts = dict(db.execute(stmt).all())
    return [
        {
            "status": status,
            "label": NORMALIZED_STATUS_LABELS[status],
            "count": int(counts.get(status, 0)),
        }
        for status in BUCKET_ORDER
    ]


def list_waybills(
    db: Session,
    principal: Principal,
    status: str | None = None,
    carrier_code: str | None = None,
    q: str | None = None,
    page: int = 1,
    size: int = 25,
) -> dict:
    stmt = (
        select(Waybill, Carrier, NormalizedTrack)
        .join(Carrier, Carrier.id == Waybill.carrier_id)
        .outerjoin(NormalizedTrack, NormalizedTrack.waybill_id == Waybill.id)
    )
    stmt = _scope_to_client(stmt, principal)
    count_stmt = _scope_to_client(
        select(func.count()).select_from(Waybill).join(Carrier, Carrier.id == Waybill.carrier_id), principal
    )
    if status:
        stmt = stmt.where(Waybill.current_status == status)
        count_stmt = count_stmt.where(Waybill.current_status == status)
    if carrier_code:
        stmt = stmt.where(Carrier.code == carrier_code)
        count_stmt = count_stmt.where(Carrier.code == carrier_code)
    if q:
        like = f"%{q.strip()}%"
        condition = or_(
            Waybill.waybill_no.like(like),
            Waybill.client_ref.like(like),
            Waybill.origin_city.like(like),
            Waybill.dest_city.like(like),
        )
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)

    total = int(db.scalar(count_stmt) or 0)
    page = max(1, page)
    size = max(1, min(size, 100))
    rows = db.execute(stmt.order_by(Waybill.id).offset((page - 1) * size).limit(size)).all()
    return {
        "items": [serialize_waybill(waybill, carrier, track) for waybill, carrier, track in rows],
        "total": total,
        "page": page,
        "size": size,
        "carriers": carrier_options(db, principal),
    }


def serialize_event(event: TraceEvent) -> dict:
    return {
        "id": event.id,
        "carrier_event_id": event.carrier_event_id,
        "raw_status": event.raw_status,
        "seq": event.seq,
        "event_time": iso_utc(event.event_time),
        "location": event.location,
        "note": event.note,
        "raw_payload": event.raw_payload,
    }


def get_waybill(db: Session, waybill_id: int, principal: Principal) -> dict:
    row = db.execute(
        select(Waybill, Carrier)
        .join(Carrier, Carrier.id == Waybill.carrier_id)
        .where(Waybill.id == waybill_id)
    ).first()
    if row is None:
        raise AppError("NOT_FOUND", 404, detail=f"waybill {waybill_id}")
    waybill, carrier = row
    if principal.role == "client" and waybill.client_account != principal.email:
        raise AppError("FORBIDDEN", 403, detail="waybill not owned by client account")
    track = db.scalar(select(NormalizedTrack).where(NormalizedTrack.waybill_id == waybill.id))
    events = db.scalars(
        select(TraceEvent).where(TraceEvent.waybill_id == waybill.id).order_by(TraceEvent.seq, TraceEvent.id)
    ).all()
    alert = db.scalar(select(StagnationAlert).where(StagnationAlert.waybill_id == waybill.id))
    return {
        "waybill": serialize_waybill(waybill, carrier, track),
        "events": [serialize_event(event) for event in events],
        "normalized_events": (track.normalized_events if track else []) or [],
        "mapping_hits": (track.mapping_hits if track else []) or [],
        "conflicts": (track.conflicts if track else []) or [],
        "coverage": track.coverage if track else 0.0,
        "mapping_version": track.mapping_version if track else None,
        "duplicate_count": track.duplicate_count if track else 0,
        "disorder_count": track.disorder_count if track else 0,
        "unmapped_count": track.unmapped_count if track else 0,
        "alert_id": alert.id if alert else None,
        "alert_severity": alert.severity if alert else None,
        "alert_status": alert.status if alert else None,
    }
