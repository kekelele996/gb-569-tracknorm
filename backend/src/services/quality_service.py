"""承运商数据质量报表：覆盖率/重复率/乱序/冲突/限流命中 → 质量分。"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.constants.limits import (
    QUALITY_CONFLICT_WEIGHT,
    QUALITY_COVERAGE_WEIGHT,
    QUALITY_DUP_WEIGHT,
)
from src.models.carrier import Carrier
from src.models.normalized_track import NormalizedTrack
from src.models.waybill import Waybill
from src.utils.geo import round_half_up
from src.utils.timeutil import iso_utc


def carrier_quality(db: Session) -> list[dict]:
    rows = db.execute(
        select(
            Carrier,
            func.count(NormalizedTrack.id),
            func.sum(NormalizedTrack.event_count),
            func.sum(NormalizedTrack.mapped_count),
            func.sum(NormalizedTrack.unmapped_count),
            func.sum(NormalizedTrack.duplicate_count),
            func.sum(NormalizedTrack.disorder_count),
            func.sum(NormalizedTrack.conflict_count),
        )
        .join(Waybill, Waybill.carrier_id == Carrier.id)
        .join(NormalizedTrack, NormalizedTrack.waybill_id == Waybill.id)
        .group_by(Carrier.id)
        .order_by(Carrier.id)
    ).all()

    payload: list[dict] = []
    for (
        carrier,
        waybills,
        events,
        mapped,
        unmapped,
        duplicates,
        disorder,
        conflicts,
    ) in rows:
        events = int(events or 0)
        mapped = int(mapped or 0)
        unmapped = int(unmapped or 0)
        duplicates = int(duplicates or 0)
        disorder = int(disorder or 0)
        conflicts = int(conflicts or 0)
        coverage = mapped / events if events else 0.0
        dup_rate = duplicates / events if events else 0.0
        conflict_rate = conflicts / events if events else 0.0
        quality_score = (
            coverage * QUALITY_COVERAGE_WEIGHT
            + (1.0 - dup_rate) * QUALITY_DUP_WEIGHT
            + (1.0 - conflict_rate) * QUALITY_CONFLICT_WEIGHT
        )
        pull_stats = carrier.last_pull_stats or {}
        payload.append(
            {
                "carrier_id": carrier.id,
                "carrier_code": carrier.code,
                "carrier_name": carrier.name,
                "status_code_system": carrier.status_code_system,
                "waybills": int(waybills or 0),
                "events": events,
                "mapped_events": mapped,
                "unmapped_events": unmapped,
                "duplicate_events": duplicates,
                "disorder_events": disorder,
                "conflict_events": conflicts,
                "coverage": round(coverage, 4),
                "coverage_percent": round(coverage * 100, 1),
                "duplicate_rate": round(dup_rate, 4),
                "conflict_rate": round(conflict_rate, 4),
                "quality_score": round_half_up(quality_score, 3),
                "rate_limit_hits": int(pull_stats.get("rate_limit_hits") or 0),
                "last_pull_at": iso_utc(carrier.last_pull_at),
                "is_active": carrier.is_active,
                "daily_quota": carrier.daily_quota,
                "rate_limit_per_min": carrier.rate_limit_per_min,
            }
        )
    return payload
