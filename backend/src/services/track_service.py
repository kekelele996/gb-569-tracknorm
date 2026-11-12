"""轨迹归一编排：读原始事件 → 调算法 1 → 落库 NormalizedTrack + 更新运单当前状态 + 统计。"""
from __future__ import annotations

import time
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.constants.enums import NORMALIZED_STATUS_LABELS, NormalizedStatus
from src.models.carrier import Carrier
from src.models.normalized_track import NormalizedTrack
from src.models.trace_event import TraceEvent
from src.models.waybill import Waybill
from src.services import audit_service, mapping_service
from src.services.normalize_engine import normalize_waybill
from src.utils.logger import get_logger
from src.utils.timeutil import iso_utc, utcnow

logger = get_logger("track")
LAST_NORMALIZE_KEY = f"{settings.brand}:last_normalize"
STATUS_ORDER = list(NormalizedStatus)


def _redis():
    try:
        import redis

        return redis.Redis.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=2)
    except Exception:  # noqa: BLE001
        return None


def events_by_waybill(db: Session) -> dict[int, list[dict]]:
    rows = db.scalars(select(TraceEvent).order_by(TraceEvent.id)).all()
    grouped: dict[int, list[dict]] = defaultdict(list)
    for event in rows:
        grouped[event.waybill_id].append(
            {
                "carrier_event_id": event.carrier_event_id,
                "raw_status": event.raw_status,
                "seq": event.seq,
                "event_time": event.event_time,
                "location": event.location,
                "note": event.note,
            }
        )
    return grouped


def normalize_all(
    db: Session,
    actor_email: str,
    version: int | None = None,
    ip: str | None = None,
) -> dict:
    started = time.time()
    resolved_version = version or mapping_service.get_active_version(db)
    rules = mapping_service.active_rules(db, resolved_version)
    grouped = events_by_waybill(db)
    rows = db.execute(select(Waybill, Carrier).join(Carrier, Carrier.id == Waybill.carrier_id)).all()

    totals = {"events": 0, "mapped": 0, "unmapped": 0, "duplicates": 0, "disorder": 0, "conflicts": 0}
    by_status: dict[str, int] = {status.value: 0 for status in STATUS_ORDER}
    conflict_items: list[dict] = []
    tracks_by_waybill = {
        track.waybill_id: track for track in db.scalars(select(NormalizedTrack)).all()
    }
    computed_at = utcnow()

    for waybill, carrier in rows:
        result = normalize_waybill(grouped.get(waybill.id, []), carrier.code, rules)
        totals["events"] += result["event_count"]
        totals["mapped"] += result["mapped_count"]
        totals["unmapped"] += result["unmapped_count"]
        totals["duplicates"] += result["duplicate_count"]
        totals["disorder"] += result["disorder_count"]
        totals["conflicts"] += result["conflict_count"]
        by_status[result["current_status"]] = by_status.get(result["current_status"], 0) + 1

        track = tracks_by_waybill.get(waybill.id)
        if track is None:
            track = NormalizedTrack(waybill_id=waybill.id)
            db.add(track)
            tracks_by_waybill[waybill.id] = track
        track.mapping_version = resolved_version
        track.current_status = result["current_status"]
        track.normalized_events = result["normalized_events"]
        track.mapping_hits = result["mapping_hits"]
        track.conflicts = result["conflicts"]
        track.event_count = result["event_count"]
        track.mapped_count = result["mapped_count"]
        track.unmapped_count = result["unmapped_count"]
        track.duplicate_count = result["duplicate_count"]
        track.disorder_count = result["disorder_count"]
        track.conflict_count = result["conflict_count"]
        track.coverage = result["coverage"]
        track.last_event_time = result["last_event_time"]
        track.computed_at = computed_at
        waybill.current_status = result["current_status"]

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

    db.flush()
    coverage = round(totals["mapped"] / totals["events"], 4) if totals["events"] else 0.0
    duration_ms = int((time.time() - started) * 1000)
    stats = {
        "version": resolved_version,
        "active_version": mapping_service.get_active_version(db),
        "waybills": len(rows),
        "events": totals["events"],
        "mapped_events": totals["mapped"],
        "unmapped_events": totals["unmapped"],
        "duplicates": totals["duplicates"],
        "disorder": totals["disorder"],
        "conflicts": totals["conflicts"],
        "coverage": coverage,
        "coverage_percent": round(coverage * 100, 1),
        "by_status": [
            {"status": status, "label": NORMALIZED_STATUS_LABELS[status], "count": by_status.get(status, 0)}
            for status in by_status
        ],
        "conflict_items": conflict_items,
        "duration_ms": duration_ms,
        "computed_at": iso_utc(computed_at),
    }
    audit_service.record(
        db,
        actor_email=actor_email,
        actor_role="",
        action="track.normalize",
        entity="normalized_track",
        entity_id=str(resolved_version),
        detail={
            "version": resolved_version,
            "coverage": coverage,
            "conflicts": totals["conflicts"],
            "events": totals["events"],
        },
        ip=ip,
    )
    cache = _redis()
    if cache is not None:
        try:
            import json

            payload = dict(stats)
            payload.pop("conflict_items", None)
            cache.set(LAST_NORMALIZE_KEY, json.dumps(payload, ensure_ascii=False, default=str), ex=86400)
        except Exception:  # noqa: BLE001
            pass
    return stats


def cache_extra(extra: dict) -> None:
    """把停滞扫描等附加统计合并进「最近归一」缓存（不影响归一结果本身）。"""
    cache = _redis()
    if cache is None:
        return
    try:
        import json

        current = last_normalize_stats() or {}
        current.update(extra)
        cache.set(LAST_NORMALIZE_KEY, json.dumps(current, ensure_ascii=False, default=str), ex=86400)
    except Exception:  # noqa: BLE001
        pass


def last_normalize_stats() -> dict | None:
    cache = _redis()
    if cache is None:
        return None
    try:
        import json

        value = cache.get(LAST_NORMALIZE_KEY)
        return json.loads(value) if value else None
    except Exception:  # noqa: BLE001
        return None


def mapping_coverage(db: Session, version: int | None = None) -> dict:
    """映射规则页顶部统计：覆盖率、冲突、未命中、规则数（复用 evaluate_version）。"""
    resolved = version or mapping_service.get_active_version(db)
    evaluation = mapping_service.evaluate_version(db, resolved)
    return {
        "version": resolved,
        "coverage": evaluation["coverage"],
        "coverage_percent": round(evaluation["coverage"] * 100, 1),
        "conflicts": evaluation["totals"]["conflicts"],
        "unmapped_events": evaluation["totals"]["unmapped"],
        "events": evaluation["totals"]["events"],
        "by_status": evaluation["by_status"],
        "conflict_items": evaluation["conflicts"],
        "duration_ms": evaluation["duration_ms"],
    }
