"""演示配置：账号、承运商、线路运力、v1 映射规则、停滞演示样本（与 batch-plan gb-569 一致）。"""
from __future__ import annotations

from src.constants.enums import MatchType, NormalizedStatus

DEMO_PASSWORD = "Demo@2026"
DEMO_USERS = [
    ("admin@tracknorm.io", "运营主管 · 周敏", "admin"),
    ("ops@tracknorm.io", "客服专员 · 陈拓", "ops"),
    ("client@tracknorm.io", "商家 · 林岚（只读）", "client"),
]

CARRIERS = [
    {
        "code": "SHUNDA",
        "name": "顺达快递",
        "status_code_system": "顺达标准码表 v3（7 状态 + 2 异常码）",
        "api_base": "mock://carrier/shunda/track/v3",
        "daily_quota": 24000,
        "rate_limit_per_min": 120,
        "avg_latency_ms": 168.0,
        "note": "标准件主力承运商，华东起运；POD 回传用 SIGNED 别名",
    },
    {
        "code": "ANENG",
        "name": "安能快运",
        "status_code_system": "安能开放平台码表 2026.3（含历史 STALE_SCAN 码）",
        "api_base": "mock://carrier/aneng/openapi/track",
        "daily_quota": 16000,
        "rate_limit_per_min": 80,
        "avg_latency_ms": 236.0,
        "note": "零担快运，华南/华北起运；偶发历史 STALE_SCAN 码回推",
    },
    {
        "code": "DEKUN",
        "name": "德坤大件",
        "status_code_system": "德坤大件码表 DK-2026A（含转寄 FWD_AGAIN 码）",
        "api_base": "mock://carrier/dekun/dk-track/api",
        "daily_quota": 9000,
        "rate_limit_per_min": 45,
        "avg_latency_ms": 412.0,
        "note": "大件专线，西北/东北线路；转寄重发需按派送中归一",
    },
]

# (origin_region, dest_region, delivered_count, active_count)
LANE_PLANS: dict[str, list[tuple[str, str, int, int]]] = {
    "SHUNDA": [
        ("华东", "华北", 20, 14),
        ("华东", "华南", 20, 13),
        ("华南", "华东", 20, 13),
    ],
    "ANENG": [
        ("华南", "华中", 12, 8),
        ("华北", "华东", 12, 8),
        ("华东", "华北", 12, 8),
    ],
    "DEKUN": [
        ("华南", "西北", 3, 2),  # 样本不足线路：演示 insufficient_baseline
        ("华北", "东北", 11, 6),
        ("华东", "西南", 10, 8),
    ],
}

WAYBILL_PREFIX = {"SHUNDA": "SD", "ANENG": "AN", "DEKUN": "DK"}

# 停滞演示样本：(承运商, 起点大区, 终点大区, 当前阶段, 目标稳健 z, 是否归 client 账号)
LAGGARD_SPECS = [
    ("SHUNDA", "华东", "华北", NormalizedStatus.IN_TRANSIT.value, 4.2, True),
    ("SHUNDA", "华东", "华北", NormalizedStatus.OUT_FOR_DELIVERY.value, 4.6, False),
    ("SHUNDA", "华东", "华南", NormalizedStatus.ARRIVED_HUB.value, 6.2, False),
    ("ANENG", "华南", "华中", NormalizedStatus.OUT_FOR_DELIVERY.value, 4.0, True),
    ("DEKUN", "华北", "东北", NormalizedStatus.OUT_FOR_DELIVERY.value, 6.6, False),
    ("DEKUN", "华东", "西南", NormalizedStatus.IN_TRANSIT.value, 9.2, False),
]

SERVICE_LEVEL_FACTOR = {"standard": 0.85, "express": 0.75, "bulky": 0.95}

# v1 映射规则：(carrier_code, source_status, target_status, match_type, score, note)
MAPPING_RULES_V1 = [
    # 顺达快递
    ("SHUNDA", "ORDER_CREATED", "created", MatchType.EXACT.value, 1.0, "标准码表精确匹配"),
    ("SHUNDA", "COLLECTED", "collected", MatchType.EXACT.value, 1.0, "标准码表精确匹配"),
    ("SHUNDA", "TRANSIT_DEPART", "in_transit", MatchType.EXACT.value, 1.0, "标准码表精确匹配"),
    ("SHUNDA", "ARRIVE_HUB", "arrived_hub", MatchType.EXACT.value, 1.0, "标准码表精确匹配"),
    ("SHUNDA", "OUT_FOR_DELIVERY", "out_for_delivery", MatchType.EXACT.value, 1.0, "标准码表精确匹配"),
    ("SHUNDA", "SIGNED", "delivered", MatchType.ALIAS.value, 0.8, "POD 回传别名（签收）"),
    ("SHUNDA", "EXC_HOLD", "exception", MatchType.EXACT.value, 1.0, "异常码"),
    ("SHUNDA", "RETURN_BACK", "returning", MatchType.EXACT.value, 1.0, "退件码"),
    # 安能快运
    ("ANENG", "ORDER_NEW", "created", MatchType.EXACT.value, 1.0, "标准码表精确匹配"),
    ("ANENG", "PICKUP_DONE", "collected", MatchType.ALIAS.value, 0.8, "揽收别名（PICKUP_DONE）"),
    ("ANENG", "LINEHAUL_START", "in_transit", MatchType.EXACT.value, 1.0, "标准码表精确匹配"),
    ("ANENG", "HUB_IN", "arrived_hub", MatchType.ALIAS.value, 0.8, "到分拨别名"),
    ("ANENG", "DELIVERING", "out_for_delivery", MatchType.EXACT.value, 1.0, "标准码表精确匹配"),
    ("ANENG", "POD_SIGNED", "delivered", MatchType.EXACT.value, 1.0, "标准码表精确匹配"),
    ("ANENG", "STALE_SCAN", "in_transit", MatchType.FUZZY.value, 0.55, "历史遗留码，模糊 0.55（待承运商确认）"),
    ("ANENG", "EXC_DELAY", "exception", MatchType.EXACT.value, 1.0, "异常码"),
    ("ANENG", "RETURN_SHIP", "returning", MatchType.EXACT.value, 1.0, "退件码"),
    # 德坤大件
    ("DEKUN", "CREATE_SO", "created", MatchType.EXACT.value, 1.0, "标准码表精确匹配"),
    ("DEKUN", "PICKED", "collected", MatchType.ALIAS.value, 0.8, "揽收别名（PICKED）"),
    ("DEKUN", "TRUNK_MOVE", "in_transit", MatchType.EXACT.value, 1.0, "标准码表精确匹配"),
    ("DEKUN", "HUB_ARRIVE", "arrived_hub", MatchType.EXACT.value, 1.0, "标准码表精确匹配"),
    ("DEKUN", "DELIVERY_OUT", "out_for_delivery", MatchType.ALIAS.value, 0.8, "派送别名"),
    ("DEKUN", "SIGN_CONFIRM", "delivered", MatchType.EXACT.value, 1.0, "标准码表精确匹配"),
    ("DEKUN", "FWD_AGAIN", "in_transit", MatchType.FUZZY.value, 0.62, "转寄重发原按运输中模糊处理（v2 修正）"),
    ("DEKUN", "EXC_ABNORMAL", "exception", MatchType.EXACT.value, 1.0, "异常码"),
    ("DEKUN", "RETURN_BUILD", "returning", MatchType.EXACT.value, 1.0, "退件码"),
]

# 历史脏数据 fixture（seed 固定注入，mock 不返回）：
UNMAPPED_CODES = ["NEW_CODE_901", "NEW_CODE_902", "NEW_CODE_903"]
CONFLICT_CODES = {"DEKUN": "FWD_AGAIN", "ANENG": "STALE_SCAN"}
DUPLICATE_OFFSET_MINUTES = (5, 9, 12, 16, 21, 25)
