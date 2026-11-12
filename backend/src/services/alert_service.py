"""停滞预警查询与处置（认领 / 处置留痕）。"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.constants.enums import (
    AlertSeverity,
    AlertStatus,
    DISPOSITION_LABELS,
    NORMALIZED_STATUS_LABELS,
)
from src.middlewares.rbac import Principal
from src.models.carrier import Carrier
from src.models.normalized_track import NormalizedTrack
from src.models.stagnation_alert import StagnationAlert
from src.models.waybill import Waybill
from src.services import audit_service
from src.utils.errors import AppError
from src.utils.geo import lane_key
from src.utils.timeutil import iso_utc, utcnow


def _scope(stmt, principal: Principal):
    if principal.role == "client":
        return stmt.where(Waybill.client_account == principal.email)
    return stmt


def serialize_alert(alert: StagnationAlert, waybill: Waybill, carrier: Carrier, track: NormalizedTrack | None) -> dict:
    timeline = []
    if track is not None:
        for event in track.normalized_events or []:
            timeline.append(
                {
                    "carrier_event_id": event.get("carrier_event_id"),
                    "raw_status": event.get("raw_status"),
                    "target_status": event.get("target_status"),
                    "target_label": NORMALIZED_STATUS_LABELS.get(event.get("target_status"), event.get("target_status")),
                    "match_type": event.get("match_type"),
                    "score": event.get("score"),
                    "event_time": event.get("event_time"),
                    "location": event.get("location"),
                }
            )
    return {
        "id": alert.id,
        "waybill_id": alert.waybill_id,
        "waybill_no": waybill.waybill_no,
        "client_account": waybill.client_account,
        "client_ref": waybill.client_ref,
        "carrier_code": carrier.code,
        "carrier_name": carrier.name,
        "lane_key": alert.lane_key,
        "origin_city": waybill.origin_city,
        "dest_city": waybill.dest_city,
        "stage": alert.stage,
        "stage_label": NORMALIZED_STATUS_LABELS.get(alert.stage, alert.stage),
        "baseline_p50_minutes": alert.baseline_p50_minutes,
        "baseline_mad_minutes": alert.baseline_mad_minutes,
        "baseline_samples": alert.baseline_samples,
        "dwell_minutes": alert.dwell_minutes,
        "robust_z": alert.robust_z,
        "severity": alert.severity,
        "status": alert.status,
        "claimed_by": alert.claimed_by,
        "claimed_at": iso_utc(alert.claimed_at),
        "disposition": alert.disposition,
        "disposition_label": DISPOSITION_LABELS.get(alert.disposition or "", alert.disposition),
        "note": alert.note,
        "predicted_delivery_at": iso_utc(alert.predicted_delivery_at),
        "promised_delivery_at": iso_utc(alert.promised_delivery_at),
        "deviation_hours": alert.deviation_hours,
        "detected_at": iso_utc(alert.detected_at),
        "handled_at": iso_utc(alert.handled_at),
        "timeline": timeline,
    }


def list_alerts(
    db: Session,
    principal: Principal,
    status: str | None = None,
    severity: str | None = None,
) -> dict:
    stmt = (
        select(StagnationAlert, Waybill, Carrier, NormalizedTrack)
        .join(Waybill, Waybill.id == StagnationAlert.waybill_id)
        .join(Carrier, Carrier.id == Waybill.carrier_id)
        .outerjoin(NormalizedTrack, NormalizedTrack.waybill_id == Waybill.id)
    )
    stmt = _scope(stmt, principal)
    if status:
        stmt = stmt.where(StagnationAlert.status == status)
    if severity:
        stmt = stmt.where(StagnationAlert.severity == severity)
    rows = db.execute(
        stmt.order_by(StagnationAlert.robust_z.desc(), StagnationAlert.id)
    ).all()
    items = [serialize_alert(alert, waybill, carrier, track) for alert, waybill, carrier, track in rows]
    return {"items": items, "total": len(items)}


def summary(db: Session, principal: Principal) -> dict:
    stmt = (
        select(StagnationAlert.severity, StagnationAlert.status, func.count())
        .join(Waybill, Waybill.id == StagnationAlert.waybill_id)
        .group_by(StagnationAlert.severity, StagnationAlert.status)
    )
    stmt = _scope(stmt, principal)
    rows = db.execute(stmt).all()
    by_severity = {severity.value: 0 for severity in AlertSeverity}
    by_status = {status.value: 0 for status in AlertStatus}
    for severity, status, count in rows:
        by_severity[severity] = by_severity.get(severity, 0) + int(count)
        by_status[status] = by_status.get(status, 0) + int(count)
    total = sum(by_status.values())
    return {
        "total": total,
        "by_severity": by_severity,
        "by_status": by_status,
        "lane_count": len(
            {
                alert.lane_key
                for alert in db.scalars(select(StagnationAlert)).all()
            }
        ),
    }


def _load(db: Session, alert_id: int) -> StagnationAlert:
    alert = db.get(StagnationAlert, alert_id)
    if alert is None:
        raise AppError("NOT_FOUND", 404, detail=f"alert {alert_id}")
    return alert


def claim(db: Session, alert_id: int, principal: Principal, note: str | None, ip: str | None = None) -> dict:
    alert = _load(db, alert_id)
    if alert.status != AlertStatus.OPEN.value:
        raise AppError("ALERT_STATE_CONFLICT", 409, detail=f"status={alert.status}")
    alert.status = AlertStatus.CLAIMED.value
    alert.claimed_by = principal.email
    alert.claimed_at = utcnow()
    if note:
        alert.note = note
    audit_service.record(
        db,
        actor_email=principal.email,
        actor_role=principal.role,
        action="alert.claim",
        entity="stagnation_alert",
        entity_id=alert.id,
        detail={"waybill_id": alert.waybill_id, "severity": alert.severity, "note": note},
        ip=ip,
    )
    db.flush()
    return {"id": alert.id, "status": alert.status, "claimed_by": alert.claimed_by, "claimed_at": iso_utc(alert.claimed_at)}


def dispose(
    db: Session,
    alert_id: int,
    principal: Principal,
    disposition: str,
    note: str | None,
    ip: str | None = None,
) -> dict:
    alert = _load(db, alert_id)
    if alert.status not in (AlertStatus.OPEN.value, AlertStatus.CLAIMED.value):
        raise AppError("ALERT_STATE_CONFLICT", 409, detail=f"status={alert.status}")
    alert.status = (
        AlertStatus.DISMISSED.value if disposition == "dismissed" else AlertStatus.HANDLED.value
    )
    alert.disposition = disposition
    alert.note = note or alert.note
    alert.claimed_by = alert.claimed_by or principal.email
    alert.handled_at = utcnow()
    audit_service.record(
        db,
        actor_email=principal.email,
        actor_role=principal.role,
        action="alert.dispose",
        entity="stagnation_alert",
        entity_id=alert.id,
        detail={"waybill_id": alert.waybill_id, "disposition": disposition, "note": note},
        ip=ip,
    )
    db.flush()
    return {
        "id": alert.id,
        "status": alert.status,
        "disposition": alert.disposition,
        "disposition_label": DISPOSITION_LABELS.get(disposition, disposition),
        "handled_at": iso_utc(alert.handled_at),
        "claimed_by": alert.claimed_by,
    }
