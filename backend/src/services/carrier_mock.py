"""承运商轨迹 API 的本地 mock（后端内置，不依赖外网）。

职责：
- 按「运单 + 承运商码表」确定性生成原始轨迹事件（同一运单每次返回逐字一致，保证拉取幂等）；
- 模拟承运商接口限流：一次拉取任务的前 N 次批量调用返回 429（CarrierRateLimited），由 pull_service 退避重试。

边界（写入 TESTING.md）：mock 只返回标准码表事件，历史脏数据（重复回推 / 乱序 / 非法回退 /
未知码）由 seed 固定注入数据库，不参与拉取返回，因此重复拉取不会新增事件。
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta

from src.constants.enums import STAGE_INDEX, NormalizedStatus, PIPELINE_STATUSES
from src.constants.limits import MOCK_429_BUDGET, MOCK_BACKOFF_MS

CARRIER_STATUS_CODES: dict[str, dict[str, str]] = {
    "SHUNDA": {
        "created": "ORDER_CREATED",
        "collected": "COLLECTED",
        "in_transit": "TRANSIT_DEPART",
        "arrived_hub": "ARRIVE_HUB",
        "out_for_delivery": "OUT_FOR_DELIVERY",
        "delivered": "SIGNED",
        "exception": "EXC_HOLD",
        "returning": "RETURN_BACK",
    },
    "ANENG": {
        "created": "ORDER_NEW",
        "collected": "PICKUP_DONE",
        "in_transit": "LINEHAUL_START",
        "arrived_hub": "HUB_IN",
        "out_for_delivery": "DELIVERING",
        "delivered": "POD_SIGNED",
        "exception": "EXC_DELAY",
        "returning": "RETURN_SHIP",
    },
    "DEKUN": {
        "created": "CREATE_SO",
        "collected": "PICKED",
        "in_transit": "TRUNK_MOVE",
        "arrived_hub": "HUB_ARRIVE",
        "out_for_delivery": "DELIVERY_OUT",
        "delivered": "SIGN_CONFIRM",
        "exception": "EXC_ABNORMAL",
        "returning": "RETURN_BUILD",
    },
}

REGION_CITIES: dict[str, tuple[str, ...]] = {
    "华东": ("上海", "杭州", "苏州", "南京"),
    "华南": ("广州", "深圳", "东莞", "佛山"),
    "华北": ("北京", "天津", "石家庄", "太原"),
    "华中": ("武汉", "长沙", "郑州", "南昌"),
    "西北": ("西安", "兰州", "乌鲁木齐", "银川"),
    "东北": ("沈阳", "大连", "哈尔滨", "长春"),
    "西南": ("成都", "重庆", "昆明", "贵阳"),
}

# 各承运商覆盖的线路（起点大区 -> 目的地大区），seed 与前端筛选用同一份口径
CARRIER_LANES: dict[str, tuple[tuple[str, str], ...]] = {
    "SHUNDA": (("华东", "华北"), ("华东", "华南"), ("华南", "华东")),
    "ANENG": (("华南", "华中"), ("华北", "华东"), ("华东", "华北")),
    "DEKUN": (("华南", "西北"), ("华北", "东北"), ("华东", "西南")),
}

BASE_GAPS_MINUTES: dict[str, float] = {
    "collected": 45.0,        # 下单 -> 揽收
    "in_transit": 420.0,      # 揽收 -> 干线发出
    "arrived_hub": 150.0,     # 干线 -> 到达分拨
    "out_for_delivery": 110.0,  # 分拨 -> 派送
    "delivered": 70.0,        # 派送 -> 签收
}


def _stable_hash(text: str) -> int:
    return int(hashlib.sha1(text.encode("utf-8")).hexdigest()[:12], 16)


def lane_factor(carrier_code: str, lane: str) -> float:
    """线路系数：不同线路的平均时长不同（0.86 / 0.96 / 1.06 / 1.16 / 1.26）。"""
    return 0.86 + 0.4 * (_stable_hash(f"{carrier_code}:{lane}") % 5) / 4.0


def city_for(region: str, seed: str) -> str:
    cities = REGION_CITIES.get(region, ("上海",))
    return cities[_stable_hash(seed) % len(cities)]


def stage_gap_minutes(carrier_code: str, lane: str, waybill_no: str, stage: str) -> float:
    base = BASE_GAPS_MINUTES[stage]
    jitter = (_stable_hash(f"{waybill_no}:{stage}") % 9) - 4  # -4..4
    return round(base * lane_factor(carrier_code, lane) * (1.0 + 0.12 * jitter / 4.0), 1)


def build_events(waybill, carrier) -> list[dict]:
    """按运单当前 trace_stage 生成确定性原始轨迹事件（不含脏数据）。"""
    stages = list(PIPELINE_STATUSES[: STAGE_INDEX[waybill.trace_stage] + 1])
    codes = CARRIER_STATUS_CODES[carrier.code]
    lane = f"{waybill.origin_region}→{waybill.dest_region}"
    times: dict[str, datetime] = {}

    if waybill.trace_stage == NormalizedStatus.DELIVERED.value:
        times["collected"] = waybill.collected_at
        for stage in stages[2:]:
            times[stage] = times[stages[stages.index(stage) - 1]] + timedelta(
                minutes=stage_gap_minutes(carrier.code, lane, waybill.waybill_no, stage)
            )
    else:
        times[waybill.trace_stage] = waybill.last_event_at
        for index in range(len(stages) - 1, 1, -1):
            stage = stages[index]
            gap = stage_gap_minutes(carrier.code, lane, waybill.waybill_no, stage)
            times[stages[index - 1]] = times[stage] - timedelta(minutes=gap)

    times["created"] = times["collected"] - timedelta(minutes=45)

    events: list[dict] = []
    for seq, stage in enumerate(stages, start=1):
        raw_status = codes[stage]
        if stage in ("created", "collected"):
            location = f"{waybill.origin_city}·{'下单' if stage == 'created' else '揽收点'}"
        elif stage == "in_transit":
            location = f"{waybill.origin_city}·干线中转"
        elif stage == "arrived_hub":
            location = f"{waybill.dest_city}·分拨中心"
        elif stage == "out_for_delivery":
            location = f"{waybill.dest_city}·营业部"
        else:
            location = f"{waybill.dest_city}·收件地"
        events.append(
            {
                "carrier_event_id": f"{waybill.waybill_no}-E{seq:02d}",
                "raw_status": raw_status,
                "seq": seq,
                "event_time": times[stage],
                "location": location,
                "note": f"{carrier.name} {raw_status}",
                "raw_payload": {
                    "event_id": f"{waybill.waybill_no}-E{seq:02d}",
                    "carrier": carrier.code,
                    "code": raw_status,
                    "scan_site": location,
                    "device": f"PDA-{_stable_hash(waybill.waybill_no) % 90 + 10}",
                },
            }
        )
    return events


@dataclass
class CarrierRateLimited(Exception):
    carrier_code: str
    retry_after_ms: int
    hit_index: int

    def __str__(self) -> str:  # pragma: no cover - 日志用
        return f"carrier {self.carrier_code} rate limited, retry after {self.retry_after_ms}ms"


class MockCarrierClient:
    """一次拉取任务一个实例：前 `rate_limit_budget` 次批量调用返回 429，之后正常返回。"""

    def __init__(self, rate_limit_budget: int = MOCK_429_BUDGET) -> None:
        self.remaining_429 = rate_limit_budget
        self.hits = 0

    def fetch_batch(self, carrier, waybills) -> list[dict]:
        if self.remaining_429 > 0:
            retry_after = MOCK_BACKOFF_MS[self.hits % len(MOCK_BACKOFF_MS)]
            self.remaining_429 -= 1
            self.hits += 1
            raise CarrierRateLimited(carrier.code, retry_after, self.hits)
        payload: list[dict] = []
        for waybill in waybills:
            for event in build_events(waybill, carrier):
                payload.append({"waybill_no": waybill.waybill_no, **event})
        return payload
