"""报表：客户延迟说明 CSV、审计日志、拉取日志。"""
from __future__ import annotations

import csv
import io

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.constants.enums import DISPOSITION_LABELS, NORMALIZED_STATUS_LABELS
from src.middlewares.rbac import Principal
from src.models.carrier import Carrier
from src.models.stagnation_alert import StagnationAlert
from src.models.waybill import Waybill
from src.services import audit_service
from src.utils.timeutil import iso_utc

CSV_HEADER = [
    "运单号",
    "承运商",
    "商家单号",
    "线路",
    "停滞阶段",
    "停滞时长(小时)",
    "段基线P50(分钟)",
    "稳健z",
    "停滞等级",
    "承诺送达",
    "预计送达",
    "预计偏差(小时)",
    "预警状态",
    "处置动作",
    "处置说明",
    "认领客服",
]

SEVERITY_LABELS = {"warn": "关注", "alert": "预警", "critical": "严重"}


def delay_notice_rows(db: Session, principal: Principal) -> list[list[str]]:
    stmt = (
        select(StagnationAlert, Waybill, Carrier)
        .join(Waybill, Waybill.id == StagnationAlert.waybill_id)
        .join(Carrier, Carrier.id == Waybill.carrier_id)
        .order_by(StagnationAlert.robust_z.desc())
    )
    if principal.role == "client":
        stmt = stmt.where(Waybill.client_account == principal.email)
    rows = db.execute(stmt).all()
    payload: list[list[str]] = []
    for alert, waybill, carrier in rows:
        payload.append(
            [
                waybill.waybill_no,
                carrier.name,
                waybill.client_ref,
                f"{waybill.origin_region}→{waybill.dest_region}",
                NORMALIZED_STATUS_LABELS.get(alert.stage, alert.stage),
                f"{alert.dwell_minutes / 60.0:.1f}",
                f"{alert.baseline_p50_minutes:.1f}",
                f"{alert.robust_z:.2f}",
                SEVERITY_LABELS.get(alert.severity, alert.severity),
                iso_utc(alert.promised_delivery_at) or "",
                iso_utc(alert.predicted_delivery_at) or "",
                f"{alert.deviation_hours:.1f}",
                alert.status,
                DISPOSITION_LABELS.get(alert.disposition or "", alert.disposition or ""),
                (alert.note or "").replace("\n", " "),
                alert.claimed_by or "",
            ]
        )
    return payload


def delay_notice_csv(db: Session, principal: Principal) -> tuple[str, int]:
    rows = delay_notice_rows(db, principal)
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(CSV_HEADER)
    writer.writerows(rows)
    return "\ufeff" + buffer.getvalue(), len(rows)


def audit_logs(db: Session, limit: int = 60) -> dict:
    return audit_service.list_logs(db, limit=limit)


def pull_logs(db: Session, limit: int = 20) -> dict:
    return audit_service.list_logs(db, limit=limit, actions=("track.pull", "track.normalize"))
