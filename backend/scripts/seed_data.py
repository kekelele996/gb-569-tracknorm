"""演示数据生成（确定性）：200 运单 / 1200 事件（含 115 重复回推、14 乱序、5 非法回退、30 未知码）。

同一 anchor 时刻生成的数据逐字一致；anchor 由 seed 写入 Redis，归一/停滞检测复用同一时刻，
保证「跑两次 seed 结果一致」且停滞条数稳定为 6。
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from types import SimpleNamespace

from src.constants.enums import STAGE_INDEX, NormalizedStatus, PIPELINE_STATUSES
from src.constants.limits import MAD_FLOOR_MINUTES, ROBUST_Z_K
from src.services.carrier_mock import CARRIER_STATUS_CODES, build_events, city_for
from src.services.normalize_engine import normalize_waybill
from src.services.stagnation_engine import median, median_absolute_deviation, stage_dwells
from scripts.demo_config import (
    CARRIERS,
    CONFLICT_CODES,
    DUPLICATE_OFFSET_MINUTES,
    LAGGARD_SPECS,
    LANE_PLANS,
    MAPPING_RULES_V1,
    SERVICE_LEVEL_FACTOR,
    UNMAPPED_CODES,
    WAYBILL_PREFIX,
)

TOTAL_WAYBILLS = 200
TOTAL_EVENTS = 1200
FIXTURE_DISORDER = 14
FIXTURE_CONFLICTS = 5
FIXTURE_UNMAPPED = 30
CLIENT_ACCOUNT = "client@tracknorm.io"
OTHER_ACCOUNTS = ("merchant-cs@shop.example", "merchant-hw@shop.example")

CARRIER_BY_CODE = {item["code"]: item for item in CARRIERS}


def _hash(text: str) -> int:
    return int(hashlib.sha1(text.encode("utf-8")).hexdigest()[:12], 16)


@dataclass
class WaybillPlan:
    waybill_no: str
    carrier_code: str
    client_account: str
    client_ref: str
    origin_region: str
    dest_region: str
    origin_city: str
    dest_city: str
    service_level: str
    weight_kg: float
    trace_stage: str
    collected_at: datetime
    last_event_at: datetime
    promised_delivery_at: datetime
    events: list[dict] = field(default_factory=list)


def _carrier_stub(code: str) -> SimpleNamespace:
    config = CARRIER_BY_CODE[code]
    return SimpleNamespace(code=code, name=config["name"])


def _waybill_stub(plan: WaybillPlan) -> SimpleNamespace:
    return SimpleNamespace(
        waybill_no=plan.waybill_no,
        trace_stage=plan.trace_stage,
        collected_at=plan.collected_at,
        last_event_at=plan.last_event_at,
        origin_region=plan.origin_region,
        dest_region=plan.dest_region,
        origin_city=plan.origin_city,
        dest_city=plan.dest_city,
    )


def _rules_for_engine() -> list[dict]:
    return [
        {
            "id": index + 1,
            "carrier_code": carrier_code,
            "source_status": source_status,
            "target_status": target_status,
            "match_type": match_type,
            "score": score,
        }
        for index, (carrier_code, source_status, target_status, match_type, score, _note) in enumerate(
            MAPPING_RULES_V1
        )
    ]


def _client_account(index: int, force_client: bool) -> str:
    if force_client or index % 5 == 0:
        return CLIENT_ACCOUNT
    return OTHER_ACCOUNTS[index % len(OTHER_ACCOUNTS)]


def _service_level(seed: str) -> tuple[str, float]:
    bucket = _hash(seed) % 5
    if bucket == 0:
        return "bulky", round(28.0 + (_hash(seed + "w") % 60) / 1.0, 1)
    if bucket == 1:
        return "express", round(0.5 + (_hash(seed + "w") % 25) / 10.0, 1)
    return "standard", round(1.0 + (_hash(seed + "w") % 140) / 10.0, 1)


def _build_plan(
    carrier_code: str,
    origin_region: str,
    dest_region: str,
    index: int,
    trace_stage: str,
    collected_at: datetime,
    last_event_at: datetime | None,
    force_client: bool,
) -> WaybillPlan:
    prefix = WAYBILL_PREFIX[carrier_code]
    waybill_no = f"{prefix}{collected_at:%Y%m%d}{index:04d}"
    service_level, weight = _service_level(waybill_no)
    plan = WaybillPlan(
        waybill_no=waybill_no,
        carrier_code=carrier_code,
        client_account=_client_account(index, force_client),
        client_ref=f"SO-2026-{index:05d}",
        origin_region=origin_region,
        dest_region=dest_region,
        origin_city=city_for(origin_region, waybill_no + "o"),
        dest_city=city_for(dest_region, waybill_no + "d"),
        service_level=service_level,
        weight_kg=weight,
        trace_stage=trace_stage,
        collected_at=collected_at,
        last_event_at=last_event_at or collected_at,
        promised_delivery_at=collected_at,
    )
    plan.events = build_events(_waybill_stub(plan), _carrier_stub(carrier_code))
    if trace_stage == NormalizedStatus.DELIVERED.value:
        plan.last_event_at = plan.events[-1]["event_time"]
    else:
        plan.collected_at = plan.events[1]["event_time"]
        plan.last_event_at = plan.events[-1]["event_time"]
    return plan


def _append_fixture_event(plan: WaybillPlan, raw_status: str, event_time: datetime, location: str, tag: str) -> None:
    plan.events.append(
        {
            "carrier_event_id": f"{plan.waybill_no}-{tag}",
            "raw_status": raw_status,
            "seq": plan.events[-1]["seq"] + 1 if plan.events else 1,
            "event_time": event_time,
            "location": location,
            "note": f"历史脏数据 fixture（{tag}）",
            "raw_payload": {"tag": tag, "carrier": plan.carrier_code, "code": raw_status},
        }
    )


def _lane_total_p50(lane_samples: dict[tuple[str, str], list[float]]) -> dict[tuple[str, str], float]:
    return {key: median(values) for key, values in lane_samples.items() if values}


def build_seed_data(anchor: datetime) -> dict:
    plans: list[WaybillPlan] = []
    rules = _rules_for_engine()
    delivered: list[WaybillPlan] = []
    index = 0

    # 1) 已签收运单（用于线路/阶段基线）
    for carrier_code, lanes in LANE_PLANS.items():
        for origin_region, dest_region, delivered_count, _active_count in lanes:
            for local in range(delivered_count):
                index += 1
                hours_ago = 40 + (_hash(f"{carrier_code}{origin_region}{local}") % 56)
                collected_at = anchor - timedelta(hours=hours_ago, minutes=local * 7 % 60)
                plan = _build_plan(
                    carrier_code, origin_region, dest_region, index,
                    NormalizedStatus.DELIVERED.value, collected_at, None, False,
                )
                delivered.append(plan)
                plans.append(plan)

    # 2) 从已签收运单推导各线路各阶段 P50 / MAD
    stage_samples: dict[tuple[str, str, str], list[float]] = {}
    lane_samples: dict[tuple[str, str], list[float]] = {}
    for plan in delivered:
        result = normalize_waybill(plan.events, plan.carrier_code, rules)
        dwells, total = stage_dwells(result["normalized_events"])
        lane = f"{plan.origin_region}→{plan.dest_region}"
        if total > 0:
            lane_samples.setdefault((plan.carrier_code, lane), []).append(total)
        for stage, minutes in dwells:
            if minutes > 0:
                stage_samples.setdefault((plan.carrier_code, lane, stage), []).append(minutes)

    baselines: dict[tuple[str, str, str], dict] = {}
    for key, values in stage_samples.items():
        center = median(values)
        baselines[key] = {
            "p50": center,
            "mad": median_absolute_deviation(values, center),
            "samples": len(values),
        }
    lane_totals = _lane_total_p50(lane_samples)

    # 3) 停滞演示样本（6 条）：z 由基线反推停留时长，保证分级固定
    laggard_plans: list[WaybillPlan] = []
    laggard_lane_counter: dict[tuple[str, str], int] = {}
    for carrier_code, origin_region, dest_region, stage, target_z, force_client in LAGGARD_SPECS:
        lane = f"{origin_region}→{dest_region}"
        baseline = baselines.get((carrier_code, lane, stage))
        if baseline is None or baseline["samples"] < 5:
            raise RuntimeError(f"laggard baseline missing: {carrier_code} {lane} {stage}")
        mad_eff = max(baseline["mad"], MAD_FLOOR_MINUTES)
        dwell_minutes = baseline["p50"] + target_z * mad_eff / ROBUST_Z_K
        index += 1
        last_event_at = anchor - timedelta(minutes=dwell_minutes)
        plan = _build_plan(
            carrier_code, origin_region, dest_region, index, stage,
            anchor - timedelta(days=2), last_event_at, force_client,
        )
        laggard_plans.append(plan)
        laggard_lane_counter[(carrier_code, lane)] = laggard_lane_counter.get((carrier_code, lane), 0) + 1
        plans.append(plan)

    # 4) 其他在途运单：阶段按哈希分配，停留取基线 1.0–1.25 倍（不触发停滞）
    active_plans: list[WaybillPlan] = []
    stage_pool = (
        NormalizedStatus.IN_TRANSIT.value,
        NormalizedStatus.ARRIVED_HUB.value,
        NormalizedStatus.OUT_FOR_DELIVERY.value,
    )
    for carrier_code, lanes in LANE_PLANS.items():
        for origin_region, dest_region, _delivered_count, active_count in lanes:
            lane = f"{origin_region}→{dest_region}"
            remaining = active_count - laggard_lane_counter.get((carrier_code, lane), 0)
            for local in range(max(0, remaining)):
                index += 1
                seed = f"{carrier_code}{lane}{local}"
                stage = stage_pool[_hash(seed) % len(stage_pool)]
                baseline = baselines.get((carrier_code, lane, stage))
                if baseline is None:
                    raise RuntimeError(f"active baseline missing: {carrier_code} {lane} {stage}")
                # 正常在途单：停留取基线 1.0 倍 + 上限，保证 z ∈ [0, 2.0]（不触发 |z|≥3.5 停滞）
                mad_eff = max(baseline["mad"], MAD_FLOOR_MINUTES)
                cap = min(0.25, 2.0 * mad_eff / (ROBUST_Z_K * max(baseline["p50"], 1.0)))
                factor = 1.0 + cap * ((_hash(seed + "f") % 10) / 9.0)
                dwell = baseline["p50"] * factor
                last_event_at = anchor - timedelta(minutes=dwell)
                plan = _build_plan(
                    carrier_code, origin_region, dest_region, index, stage,
                    anchor - timedelta(days=2), last_event_at, False,
                )
                active_plans.append(plan)
                plans.append(plan)

    # 5) 承诺送达：线路总时长 P50 × 服务等级系数（承运商承诺略紧于自身平均）
    for plan in plans:
        lane = f"{plan.origin_region}→{plan.dest_region}"
        total_p50 = lane_totals.get((plan.carrier_code, lane), 720.0)
        factor = SERVICE_LEVEL_FACTOR.get(plan.service_level, 0.85)
        plan.promised_delivery_at = plan.collected_at + timedelta(minutes=total_p50 * factor)

    canonical_events = sum(len(plan.events) for plan in plans)
    fixture_budget = TOTAL_EVENTS - canonical_events
    duplicates_needed = fixture_budget - FIXTURE_DISORDER - FIXTURE_CONFLICTS - FIXTURE_UNMAPPED
    if duplicates_needed < 0:
        raise RuntimeError(f"canonical events too many: {canonical_events}")

    # 6) fixture A：乱序到达（14 条，seq 最大但时间更早）
    disorder_targets = sorted(active_plans, key=lambda plan: plan.waybill_no)[:FIXTURE_DISORDER]
    for plan in disorder_targets:
        code = CARRIER_STATUS_CODES[plan.carrier_code]["in_transit"]
        _append_fixture_event(
            plan, code,
            plan.collected_at + timedelta(minutes=22 + _hash(plan.waybill_no) % 7),
            f"{plan.origin_city}·干线中转", "LATE",
        )

    # 7) fixture B：非法回退（5 条：德坤 3 条转寄重发 → v2 修复；安能 2 条历史码 → 保持冲突）
    conflict_targets: dict[str, list[WaybillPlan]] = {"DEKUN": [], "ANENG": []}
    for plan in sorted(active_plans, key=lambda item: item.waybill_no):
        if plan.carrier_code in conflict_targets and plan.trace_stage == NormalizedStatus.OUT_FOR_DELIVERY.value:
            if len(conflict_targets[plan.carrier_code]) < (3 if plan.carrier_code == "DEKUN" else 2):
                conflict_targets[plan.carrier_code].append(plan)
    for carrier_code, targets in conflict_targets.items():
        for plan in targets:
            raw = CONFLICT_CODES[carrier_code]
            _append_fixture_event(
                plan, raw,
                plan.last_event_at + timedelta(minutes=30),
                f"{plan.dest_city}·转寄点", "ROLLBACK",
            )

    # 8) fixture D：重复回推（必须在未知码之前注入，复制的是最后一条已映射事件）（同状态同地点 30 分钟内），只复制每条运单最后一条事件，不新增乱序
    duplicate_pool = [plan for plan in plans]
    for cursor in range(duplicates_needed):
        plan = duplicate_pool[cursor % len(duplicate_pool)]
        last_event = plan.events[-1]
        offset = DUPLICATE_OFFSET_MINUTES[(cursor // len(duplicate_pool) + cursor) % len(DUPLICATE_OFFSET_MINUTES)]
        _append_fixture_event(
            plan, last_event["raw_status"], last_event["event_time"] + timedelta(minutes=offset),
            last_event["location"], f"DUP{cursor + 1:03d}",
        )

    # 9) fixture C：未知状态码（追加在最后，时间递增不引入乱序）（30 条 = 10 单 × 3 条，时间在最后事件之后，不影响乱序指标）
    unmapped_targets = sorted(plans, key=lambda plan: plan.waybill_no)[::20][:10]
    for plan in unmapped_targets:
        for offset, code in enumerate(UNMAPPED_CODES, start=1):
            _append_fixture_event(
                plan, code,
                plan.last_event_at + timedelta(minutes=40 * offset),
                f"{plan.dest_city}·扫描点", f"UNMAPPED{offset}",
            )

    total_events = sum(len(plan.events) for plan in plans)
    if total_events != TOTAL_EVENTS:
        raise RuntimeError(f"event total {total_events} != {TOTAL_EVENTS}")
    if len(plans) != TOTAL_WAYBILLS:
        raise RuntimeError(f"waybill total {len(plans)} != {TOTAL_WAYBILLS}")

    stats = {
        "anchor": anchor,
        "waybills": len(plans),
        "delivered": len(delivered),
        "active": len(active_plans) + len(laggard_plans),
        "laggards": len(laggard_plans),
        "canonical_events": canonical_events,
        "duplicate_events": duplicates_needed,
        "disorder_events": FIXTURE_DISORDER,
        "conflict_events": FIXTURE_CONFLICTS,
        "unmapped_events": FIXTURE_UNMAPPED,
        "events": total_events,
        "lanes": len(lane_totals),
        "stage_baselines": len(baselines),
    }
    return {"plans": plans, "baselines": baselines, "lane_totals": lane_totals, "stats": stats}
