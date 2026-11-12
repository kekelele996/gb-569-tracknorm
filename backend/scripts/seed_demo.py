"""幂等 seed：3 账号 / 3 承运商 / 26 条 v1 映射规则 / 200 运单 / 1200 轨迹事件 / 6 条停滞预警。

自然键 upsert：users.email、carriers.code、status_mappings(version,carrier,source)、
waybills.waybill_no、trace_events(waybill,carrier_event_id)、normalized_tracks.waybill_id、
stagnation_alerts.waybill_id。重复执行不新增、不覆盖用户修改。

演示锚定：首次运行把「数据锚定时刻」写入 Redis，归一/停滞检测复用同一时刻，
保证重复运行 SEED_SUMMARY 逐字一致、停滞预警稳定为 6 条。
"""
from __future__ import annotations

import sys

from sqlalchemy import func, select

from src.config.database import session_scope
from src.constants.enums import MatchType
from src.models.carrier import Carrier
from src.models.normalized_track import NormalizedTrack
from src.models.stagnation_alert import StagnationAlert
from src.models.status_mapping import StatusMapping
from src.models.trace_event import TraceEvent
from src.models.user import User
from src.models.waybill import Waybill
from src.services import mapping_service, stagnation_engine, track_service
from src.utils.security import hash_password
from scripts.demo_config import CARRIERS, DEMO_PASSWORD, DEMO_USERS, MAPPING_RULES_V1
from scripts.seed_data import build_seed_data

SEED_ACTOR = "seed@tracknorm.io"


def ensure_users(db) -> dict[str, User]:
    users: dict[str, User] = {}
    for email, display_name, role in DEMO_USERS:
        existing = db.scalar(select(User).where(User.email == email))
        if existing is None:
            existing = User(
                email=email,
                password_hash=hash_password(DEMO_PASSWORD),
                display_name=display_name,
                role=role,
            )
            db.add(existing)
            db.flush()
        users[email] = existing
    return users


def ensure_carriers(db) -> dict[str, Carrier]:
    carriers: dict[str, Carrier] = {}
    for config in CARRIERS:
        existing = db.scalar(select(Carrier).where(Carrier.code == config["code"]))
        if existing is None:
            existing = Carrier(
                code=config["code"],
                name=config["name"],
                status_code_system=config["status_code_system"],
                api_base=config["api_base"],
                daily_quota=config["daily_quota"],
                rate_limit_per_min=config["rate_limit_per_min"],
                avg_latency_ms=config["avg_latency_ms"],
                note=config["note"],
            )
            db.add(existing)
            db.flush()
        carriers[config["code"]] = existing
    return carriers


def ensure_mapping_v1(db) -> None:
    existing = db.scalar(select(func.count()).select_from(StatusMapping).where(StatusMapping.version == 1)) or 0
    if int(existing) > 0:
        return
    for carrier_code, source_status, target_status, match_type, score, note in MAPPING_RULES_V1:
        db.add(
            StatusMapping(
                version=1,
                carrier_code=carrier_code,
                source_status=source_status,
                target_status=target_status,
                match_type=match_type or MatchType.EXACT.value,
                score=score,
                is_active=True,
                note=note,
                created_by=SEED_ACTOR,
            )
        )
    db.flush()
    mapping_service.set_active_version(1)


def persist_plans(db, carriers: dict[str, Carrier], plans) -> None:
    existing_waybills = {waybill.waybill_no: waybill for waybill in db.scalars(select(Waybill)).all()}
    created = 0
    for plan in plans:
        if plan.waybill_no in existing_waybills:
            continue
        waybill = Waybill(
            waybill_no=plan.waybill_no,
            carrier_id=carriers[plan.carrier_code].id,
            client_account=plan.client_account,
            client_ref=plan.client_ref,
            origin_region=plan.origin_region,
            dest_region=plan.dest_region,
            origin_city=plan.origin_city,
            dest_city=plan.dest_city,
            service_level=plan.service_level,
            weight_kg=plan.weight_kg,
            trace_stage=plan.trace_stage,
            current_status=plan.trace_stage,
            promised_delivery_at=plan.promised_delivery_at,
            collected_at=plan.collected_at,
            last_event_at=plan.last_event_at,
        )
        db.add(waybill)
        existing_waybills[plan.waybill_no] = waybill
        created += 1
    db.flush()

    for plan in plans:
        waybill = existing_waybills[plan.waybill_no]
        existing_event_ids = set(
            db.scalars(
                select(TraceEvent.carrier_event_id).where(TraceEvent.waybill_id == waybill.id)
            ).all()
        )
        for event in plan.events:
            if event["carrier_event_id"] in existing_event_ids:
                continue
            db.add(
                TraceEvent(
                    waybill_id=waybill.id,
                    carrier_id=waybill.carrier_id,
                    carrier_event_id=event["carrier_event_id"],
                    raw_status=event["raw_status"],
                    seq=event["seq"],
                    event_time=event["event_time"],
                    location=event["location"],
                    note=event["note"],
                    raw_payload=event.get("raw_payload") or {},
                )
            )
    db.flush()


def seed_all() -> str:
    with session_scope() as db:
        ensure_users(db)
        carriers = ensure_carriers(db)
        ensure_mapping_v1(db)

        anchor = stagnation_engine.get_or_create_demo_anchor()
        existing_waybills = int(db.scalar(select(func.count()).select_from(Waybill)) or 0)
        if existing_waybills == 0:
            data = build_seed_data(anchor)
            persist_plans(db, carriers, data["plans"])
        db.flush()

        version = mapping_service.get_active_version(db)
        track_service.normalize_all(db, SEED_ACTOR, version)
        stagnation_engine.detect_and_store(db, as_of=anchor)

        summary = (
            f"SEED_SUMMARY brand=tracknorm "
            f"carriers={db.scalar(select(func.count()).select_from(Carrier))} "
            f"waybills={db.scalar(select(func.count()).select_from(Waybill))} "
            f"events={db.scalar(select(func.count()).select_from(TraceEvent))} "
            f"alerts={db.scalar(select(func.count()).select_from(StagnationAlert))} "
            f"users={db.scalar(select(func.count()).select_from(User))}"
        )
        # SEED_DETAIL 全部来自数据库聚合，重复执行逐字一致
        track_agg = db.execute(
            select(
                func.coalesce(func.sum(NormalizedTrack.duplicate_count), 0),
                func.coalesce(func.sum(NormalizedTrack.disorder_count), 0),
                func.coalesce(func.sum(NormalizedTrack.conflict_count), 0),
                func.coalesce(func.sum(NormalizedTrack.unmapped_count), 0),
            )
        ).one()
        detail = (
            f"SEED_DETAIL brand=tracknorm tracks={db.scalar(select(func.count()).select_from(NormalizedTrack))} "
            f"mappings_v1={db.scalar(select(func.count()).select_from(StatusMapping).where(StatusMapping.version == 1))} "
            f"laggards={db.scalar(select(func.count()).select_from(StagnationAlert))} dup={int(track_agg[0])} "
            f"disorder={int(track_agg[1])} rollback={int(track_agg[2])} unmapped={int(track_agg[3])}"
        )

    print(summary)
    print(detail)
    return summary


if __name__ == "__main__":
    try:
        seed_all()
    except Exception as exc:  # noqa: BLE001
        print(f"SEED_FAILED {exc}", file=sys.stderr)
        raise
