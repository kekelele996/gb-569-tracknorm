"""算法 2：停滞检测（承运商 × 线路 × 当前阶段 的稳健 z 分级）。

口径（README / TESTING 同步）：
- 基线样本：已签收运单的「同承运商 + 同线路 + 同阶段」停留时长（分钟），取 P50 与 MAD；
- 稳健 z = 0.6745 × (当前停留 − P50) / max(MAD, 1.0)；
- 只对「停留偏长」方向判定（快进不告警）：z ≥ 3.5 判停滞，分 warn(3.5–5) / alert(5–8) / critical(≥8)；
- 样本 < 5 → 失败态 insufficient_baseline（不出预警，计入统计）；
- 预计送达 = 最后事件时间 + 后续各段基线 P50 之和（已过期则取当前时刻），
  偏差（小时）= 预计送达 − 承诺送达。
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.constants.enums import (
    AlertSeverity,
    AlertStatus,
    NormalizedStatus,
    PIPELINE_STATUSES,
    STAGE_INDEX,
)
from src.constants.limits import (
    MAD_FLOOR_MINUTES,
    MIN_BASELINE_SAMPLES,
    ROBUST_Z_K,
    Z_ALERT,
    Z_CRITICAL,
    Z_WARN,
)
from src.models.carrier import Carrier
from src.models.normalized_track import NormalizedTrack
from src.models.stagnation_alert import StagnationAlert
from src.models.waybill import Waybill
from src.config.settings import settings
from src.utils.geo import lane_key, round_half_up
from src.utils.timeutil import iso_utc, parse_iso, utcnow

DEMO_ANCHOR_KEY = f"{settings.brand}:demo:as_of"


def _redis():
    try:
        import redis

        return redis.Redis.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=2)
    except Exception:  # noqa: BLE001
        return None


def get_demo_anchor() -> datetime | None:
    """演示数据锚定时刻（seed 写入），用于让重复跑批结果可复现。"""
    client = _redis()
    if client is None:
        return None
    try:
        value = client.get(DEMO_ANCHOR_KEY)
        return parse_iso(value) if value else None
    except Exception:  # noqa: BLE001
        return None


def get_or_create_demo_anchor() -> datetime:
    client = _redis()
    if client is not None:
        try:
            value = client.get(DEMO_ANCHOR_KEY)
            if value:
                parsed = parse_iso(value)
                if parsed is not None:
                    return parsed
            candidate = utcnow().replace(microsecond=0)
            client.set(DEMO_ANCHOR_KEY, iso_utc(candidate), nx=True)
            value = client.get(DEMO_ANCHOR_KEY)
            parsed = parse_iso(value) if value else None
            if parsed is not None:
                return parsed
        except Exception:  # noqa: BLE001
            pass
    return utcnow().replace(microsecond=0)


def resolve_as_of() -> datetime:
    """有演示锚点就用锚点（可复现），否则用当前时刻。"""
    return get_demo_anchor() or utcnow()

ACTIVE_STATUSES = tuple(
    status
    for status in PIPELINE_STATUSES
    if status not in (NormalizedStatus.DELIVERED.value,)
)


def median(values: list[float]) -> float:
    ordered = sorted(values)
    size = len(ordered)
    if size == 0:
        return 0.0
    middle = size // 2
    if size % 2 == 1:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2.0


def median_absolute_deviation(values: list[float], center: float) -> float:
    return median([abs(value - center) for value in values])


def stage_dwells(normalized_events: list[dict]) -> tuple[list[tuple[str, float]], float]:
    """从归一轨迹算出各阶段停留（分钟）与全程耗时。"""
    parsed: list[tuple[datetime, str]] = []
    for event in normalized_events or []:
        moment = parse_iso(event.get("event_time"))
        status = event.get("target_status")
        if moment is None or status is None:
            continue
        parsed.append((moment, status))
    if len(parsed) < 2:
        return [], 0.0
    dwells: list[tuple[str, float]] = []
    for index in range(len(parsed) - 1):
        stage = parsed[index][1]
        if stage not in STAGE_INDEX:
            continue
        minutes = (parsed[index + 1][0] - parsed[index][0]).total_seconds() / 60.0
        dwells.append((stage, minutes))
    total = (parsed[-1][0] - parsed[0][0]).total_seconds() / 60.0
    return dwells, total


def build_baselines(db: Session) -> dict:
    """从已签收运单构建阶段基线；返回 {"stages": {key: baseline}, "lanes": {key: baseline}}。"""
    rows = db.execute(
        select(NormalizedTrack, Waybill, Carrier)
        .join(Waybill, Waybill.id == NormalizedTrack.waybill_id)
        .join(Carrier, Carrier.id == Waybill.carrier_id)
    ).all()

    stage_samples: dict[tuple[str, str, str], list[float]] = {}
    lane_samples: dict[tuple[str, str], list[float]] = {}
    for track, waybill, carrier in rows:
        if track.current_status != NormalizedStatus.DELIVERED.value:
            continue
        lane = lane_key(waybill.origin_region, waybill.dest_region)
        dwells, total = stage_dwells(track.normalized_events or [])
        if total > 0:
            lane_samples.setdefault((carrier.code, lane), []).append(total)
        for stage, minutes in dwells:
            if minutes <= 0:
                continue
            stage_samples.setdefault((carrier.code, lane, stage), []).append(minutes)

    def summarize(values: list[float]) -> dict:
        center = median(values)
        return {
            "p50": round(center, 1),
            "mad": round(median_absolute_deviation(values, center), 1),
            "samples": len(values),
        }

    return {
        "stages": {key: summarize(values) for key, values in stage_samples.items()},
        "lanes": {key: summarize(values) for key, values in lane_samples.items()},
    }


def remaining_minutes(baselines: dict, carrier_code: str, lane: str, current_stage: str) -> float:
    """当前阶段之后各段基线 P50 之和 ≈ 还需要多久送达。"""
    if current_stage not in STAGE_INDEX:
        return 0.0
    later = PIPELINE_STATUSES[STAGE_INDEX[current_stage] + 1:]
    total = 0.0
    for stage in later:
        baseline = baselines["stages"].get((carrier_code, lane, stage))
        if baseline and baseline["samples"] >= MIN_BASELINE_SAMPLES:
            total += baseline["p50"]
    if total <= 0:
        lane_baseline = baselines["lanes"].get((carrier_code, lane))
        total = (lane_baseline["p50"] * 0.35) if lane_baseline else 120.0
    return total


def severity_for(z_value: float) -> str:
    if z_value >= Z_CRITICAL:
        return AlertSeverity.CRITICAL.value
    if z_value >= Z_ALERT:
        return AlertSeverity.ALERT.value
    return AlertSeverity.WARN.value


def detect_candidates(db: Session, as_of: datetime | None = None) -> tuple[list[dict], dict]:
    """扫描在途运单，输出停滞候选与统计（不作为的线路计入 insufficient_baseline）。"""
    as_of = as_of or utcnow()
    baselines = build_baselines(db)
    rows = db.execute(
        select(NormalizedTrack, Waybill, Carrier)
        .join(Waybill, Waybill.id == NormalizedTrack.waybill_id)
        .join(Carrier, Carrier.id == Waybill.carrier_id)
    ).all()

    candidates: list[dict] = []
    evaluated = 0
    insufficient = 0
    for track, waybill, carrier in rows:
        if track.current_status not in ACTIVE_STATUSES:
            continue
        evaluated += 1
        lane = lane_key(waybill.origin_region, waybill.dest_region)
        stage = track.current_status
        baseline = baselines["stages"].get((carrier.code, lane, stage))
        if (
            baseline is None
            or baseline["samples"] < MIN_BASELINE_SAMPLES
            or track.last_event_time is None
        ):
            insufficient += 1
            continue
        dwell_minutes = (as_of - track.last_event_time).total_seconds() / 60.0
        mad = max(baseline["mad"], MAD_FLOOR_MINUTES)
        robust_z = ROBUST_Z_K * (dwell_minutes - baseline["p50"]) / mad
        # 只判定「停留偏长」：负向 z（比基线更快）不是停滞，不能当成异常
        if robust_z < Z_WARN:
            continue
        remaining = remaining_minutes(baselines, carrier.code, lane, stage)
        predicted = max(as_of, track.last_event_time + timedelta(minutes=remaining))
        promised = waybill.promised_delivery_at
        deviation_hours = round_half_up((predicted - promised).total_seconds() / 3600.0, 1) if promised else 0.0
        candidates.append(
            {
                "waybill_id": waybill.id,
                "waybill_no": waybill.waybill_no,
                "carrier_code": carrier.code,
                "carrier_name": carrier.name,
                "carrier_id": carrier.id,
                "lane_key": lane,
                "stage": stage,
                "baseline_p50_minutes": baseline["p50"],
                "baseline_mad_minutes": baseline["mad"],
                "baseline_samples": baseline["samples"],
                "dwell_minutes": round(dwell_minutes, 1),
                "robust_z": round(robust_z, 2),
                "severity": severity_for(robust_z),
                "predicted_delivery_at": predicted,
                "promised_delivery_at": promised,
                "deviation_hours": deviation_hours,
            }
        )

    stats = {
        "as_of": as_of,
        "evaluated": evaluated,
        "candidates": len(candidates),
        "insufficient_baseline": insufficient,
        "baseline_stage_keys": len(baselines["stages"]),
        "warning": None,
    }
    return candidates, stats


def upsert_alerts(db: Session, candidates: list[dict], as_of: datetime) -> dict:
    """按 waybill 自然键 upsert 预警：已认领/已处置的保留状态与处置留痕。"""
    created = 0
    updated = 0
    preserved = 0
    for candidate in candidates:
        existing = db.scalar(
            select(StagnationAlert).where(StagnationAlert.waybill_id == candidate["waybill_id"])
        )
        if existing is None:
            db.add(
                StagnationAlert(
                    waybill_id=candidate["waybill_id"],
                    carrier_id=candidate["carrier_id"],
                    lane_key=candidate["lane_key"],
                    stage=candidate["stage"],
                    baseline_p50_minutes=candidate["baseline_p50_minutes"],
                    baseline_mad_minutes=candidate["baseline_mad_minutes"],
                    baseline_samples=candidate["baseline_samples"],
                    dwell_minutes=candidate["dwell_minutes"],
                    robust_z=candidate["robust_z"],
                    severity=candidate["severity"],
                    predicted_delivery_at=candidate["predicted_delivery_at"],
                    promised_delivery_at=candidate["promised_delivery_at"],
                    deviation_hours=candidate["deviation_hours"],
                    status=AlertStatus.OPEN.value,
                    detected_at=as_of,
                )
            )
            created += 1
            continue
        existing.baseline_p50_minutes = candidate["baseline_p50_minutes"]
        existing.baseline_mad_minutes = candidate["baseline_mad_minutes"]
        existing.baseline_samples = candidate["baseline_samples"]
        existing.dwell_minutes = candidate["dwell_minutes"]
        existing.robust_z = candidate["robust_z"]
        existing.severity = candidate["severity"]
        existing.predicted_delivery_at = candidate["predicted_delivery_at"]
        existing.deviation_hours = candidate["deviation_hours"]
        if existing.status == AlertStatus.OPEN.value:
            existing.detected_at = as_of
            updated += 1
        else:
            preserved += 1
    db.flush()
    return {"created": created, "updated": updated, "preserved": preserved}


def detect_and_store(db: Session, as_of: datetime | None = None) -> dict:
    as_of = as_of or resolve_as_of()
    candidates, stats = detect_candidates(db, as_of)
    upsert_stats = upsert_alerts(db, candidates, as_of)
    stats.update(upsert_stats)
    stats["as_of"] = as_of.isoformat(timespec="seconds") + "Z"
    return stats
