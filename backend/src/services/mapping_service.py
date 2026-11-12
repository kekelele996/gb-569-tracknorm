"""状态映射规则版本管理：v1 基线、v2 冲突修复版本、版本统计（覆盖率/冲突）。"""
from __future__ import annotations

import time
from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.constants.enums import NORMALIZED_STATUS_LABELS, NormalizedStatus
from src.constants.limits import ALIAS_SCORE
from src.models.carrier import Carrier
from src.models.status_mapping import StatusMapping
from src.models.trace_event import TraceEvent
from src.models.waybill import Waybill
from src.services.normalize_engine import normalize_waybill
from src.utils.errors import AppError
from src.utils.timeutil import iso_utc, utcnow

ACTIVE_VERSION_KEY = f"{settings.brand}:mapping:active_version"
# v2 修复口径：转寄重发（FWD_AGAIN）按业务定义仍属派送中，别名 0.8 覆盖 v1 的模糊 0.62
UPGRADED_RULES = (
    {
        "carrier_code": "DEKUN",
        "source_status": "FWD_AGAIN",
        "target_status": NormalizedStatus.OUT_FOR_DELIVERY.value,
        "match_type": "alias",
        "score": ALIAS_SCORE,
        "note": "v2：转寄重发仍属派送中（别名 0.8，覆盖 v1 模糊 0.62，修复 3 起非法回退）",
    },
)


def _redis():
    try:
        import redis

        return redis.Redis.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=2)
    except Exception:  # noqa: BLE001
        return None


def get_active_version(db: Session) -> int:
    client = _redis()
    if client is not None:
        try:
            value = client.get(ACTIVE_VERSION_KEY)
            if value:
                return int(value)
        except Exception:  # noqa: BLE001
            pass
    latest = db.scalar(select(func.max(StatusMapping.version)))
    return int(latest or settings.mapping_default_version)


def set_active_version(version: int) -> None:
    client = _redis()
    if client is None:
        return
    try:
        client.set(ACTIVE_VERSION_KEY, version)
    except Exception:  # noqa: BLE001
        pass


def serialize_rule(rule: StatusMapping, hits: int = 0, conflicts: int = 0) -> dict:
    return {
        "id": rule.id,
        "version": rule.version,
        "carrier_code": rule.carrier_code,
        "source_status": rule.source_status,
        "target_status": rule.target_status,
        "target_label": NORMALIZED_STATUS_LABELS.get(rule.target_status, rule.target_status),
        "match_type": rule.match_type,
        "score": rule.score,
        "is_active": rule.is_active,
        "note": rule.note,
        "hits": hits,
        "conflicts": conflicts,
        "created_at": iso_utc(rule.created_at),
    }


def list_versions(db: Session) -> list[dict]:
    rows = db.execute(
        select(StatusMapping.version, func.count(), func.min(StatusMapping.created_at))
        .group_by(StatusMapping.version)
        .order_by(StatusMapping.version)
    ).all()
    active = get_active_version(db)
    return [
        {
            "version": int(version),
            "rules": int(count),
            "created_at": iso_utc(created_at),
            "is_active": int(version) == active,
        }
        for version, count, created_at in rows
    ]


def active_rules(db: Session, version: int | None = None) -> list[dict]:
    resolved = version or get_active_version(db)
    rules = db.scalars(
        select(StatusMapping)
        .where(StatusMapping.version == resolved, StatusMapping.is_active.is_(True))
        .order_by(StatusMapping.carrier_code, StatusMapping.source_status)
    ).all()
    return [
        {
            "id": rule.id,
            "carrier_code": rule.carrier_code,
            "source_status": rule.source_status,
            "target_status": rule.target_status,
            "match_type": rule.match_type,
            "score": rule.score,
        }
        for rule in rules
    ]


def rule_hits_from_tracks(db: Session, version: int) -> tuple[dict[int, int], dict[int, int]]:
    hits: dict[int, int] = defaultdict(int)
    conflicts: dict[int, int] = defaultdict(int)
    from src.models.normalized_track import NormalizedTrack

    tracks = db.scalars(select(NormalizedTrack).where(NormalizedTrack.mapping_version == version)).all()
    for track in tracks:
        for hit in track.mapping_hits or []:
            rule_id = hit.get("rule_id")
            if rule_id is None:
                continue
            hits[rule_id] += int(hit.get("hits") or 0)
            conflicts[rule_id] += int(hit.get("conflicts") or 0)
    return hits, conflicts


def list_rules(db: Session, version: int | None = None) -> dict:
    resolved = version or get_active_version(db)
    hits, conflicts = rule_hits_from_tracks(db, resolved)
    rules = db.scalars(
        select(StatusMapping)
        .where(StatusMapping.version == resolved)
        .order_by(StatusMapping.carrier_code, StatusMapping.target_status, StatusMapping.source_status)
    ).all()
    return {
        "version": resolved,
        "active_version": get_active_version(db),
        "rules": [serialize_rule(rule, hits.get(rule.id, 0), conflicts.get(rule.id, 0)) for rule in rules],
    }


def evaluate_version(db: Session, version: int) -> dict:
    """在内存中重算某版本的归一结果（不落库），用于映射规则页对比 v1/v2。"""
    started = time.time()
    rules = active_rules(db, version)
    rows = db.execute(select(Waybill, Carrier).join(Carrier, Carrier.id == Waybill.carrier_id)).all()
    event_rows = db.scalars(select(TraceEvent)).all()
    events_by_waybill: dict[int, list[dict]] = defaultdict(list)
    for event in event_rows:
        events_by_waybill[event.waybill_id].append(
            {
                "carrier_event_id": event.carrier_event_id,
                "raw_status": event.raw_status,
                "seq": event.seq,
                "event_time": event.event_time,
                "location": event.location,
                "note": event.note,
            }
        )

    totals = {
        "events": 0,
        "mapped": 0,
        "unmapped": 0,
        "duplicates": 0,
        "disorder": 0,
        "conflicts": 0,
        "waybills": 0,
    }
    by_status: dict[str, int] = {status.value: 0 for status in NormalizedStatus}
    conflict_items: list[dict] = []
    rule_stats: dict[int, dict] = {}
    for waybill, carrier in rows:
        result = normalize_waybill(events_by_waybill.get(waybill.id, []), carrier.code, rules)
        totals["waybills"] += 1
        totals["events"] += result["event_count"]
        totals["mapped"] += result["mapped_count"]
        totals["unmapped"] += result["unmapped_count"]
        totals["duplicates"] += result["duplicate_count"]
        totals["disorder"] += result["disorder_count"]
        totals["conflicts"] += result["conflict_count"]
        by_status[result["current_status"]] = by_status.get(result["current_status"], 0) + 1
        for conflict in result["conflicts"]:
            conflict_items.append(
                {
                    "waybill_id": waybill.id,
                    "waybill_no": waybill.waybill_no,
                    "carrier_code": carrier.code,
                    "raw_status": conflict["raw_status"],
                    "from_status": conflict["from_status"],
                    "to_status": conflict["to_status"],
                    "event_time": conflict["event_time"],
                    "reason_label": conflict["reason_label"],
                }
            )
        for hit in result["mapping_hits"]:
            rule_id = hit.get("rule_id")
            if rule_id is None:
                continue
            entry = rule_stats.setdefault(rule_id, {"hits": 0, "conflicts": 0})
            entry["hits"] += hit["hits"]
            entry["conflicts"] += hit["conflicts"]

    coverage = round(totals["mapped"] / totals["events"], 4) if totals["events"] else 0.0
    return {
        "version": version,
        "active_version": get_active_version(db),
        "coverage": coverage,
        "totals": totals,
        "by_status": [
            {"status": status.value, "label": NORMALIZED_STATUS_LABELS[status.value], "count": by_status.get(status.value, 0)}
            for status in NormalizedStatus
        ],
        "conflicts": conflict_items,
        "rule_stats": [{"rule_id": key, **value} for key, value in rule_stats.items()],
        "duration_ms": int((time.time() - started) * 1000),
    }


def create_version(db: Session, base_version: int, actor: str, note: str | None = None) -> dict:
    latest = db.scalar(select(func.max(StatusMapping.version))) or 0
    new_version = int(latest) + 1
    existing = db.scalars(select(StatusMapping).where(StatusMapping.version == new_version)).first()
    if existing is not None:
        raise AppError("MAPPING_VERSION_CONFLICT", 409, detail=f"version {new_version}")
    base_rules = db.scalars(select(StatusMapping).where(StatusMapping.version == base_version)).all()
    if not base_rules:
        raise AppError("MAPPING_VERSION_CONFLICT", 404, detail=f"base version {base_version}")
    upgraded_keys = {(rule["carrier_code"], rule["source_status"]) for rule in UPGRADED_RULES}
    copied = 0
    for rule in base_rules:
        if (rule.carrier_code, rule.source_status) in upgraded_keys:
            continue
        db.add(
            StatusMapping(
                version=new_version,
                carrier_code=rule.carrier_code,
                source_status=rule.source_status,
                target_status=rule.target_status,
                match_type=rule.match_type,
                score=rule.score,
                is_active=True,
                note=rule.note,
                created_by=actor,
            )
        )
        copied += 1
    for rule in UPGRADED_RULES:
        db.add(
            StatusMapping(
                version=new_version,
                carrier_code=rule["carrier_code"],
                source_status=rule["source_status"],
                target_status=rule["target_status"],
                match_type=rule["match_type"],
                score=rule["score"],
                is_active=True,
                note=rule["note"],
                created_by=actor,
            )
        )
    db.flush()
    return {
        "version": new_version,
        "base_version": base_version,
        "copied_rules": copied,
        "added_rules": len(UPGRADED_RULES),
        "note": note or "v2：新增转寄重发别名规则，修复非法回退冲突",
        "created_by": actor,
        "created_at": iso_utc(utcnow()),
    }


def activate_version(db: Session, version: int, actor: str) -> dict:
    count = db.scalar(
        select(func.count()).select_from(StatusMapping).where(StatusMapping.version == version)
    ) or 0
    if int(count) == 0:
        raise AppError("MAPPING_VERSION_CONFLICT", 404, detail=f"version {version}")
    set_active_version(version)
    return {"version": version, "rules": int(count), "activated_by": actor, "activated_at": iso_utc(utcnow())}
