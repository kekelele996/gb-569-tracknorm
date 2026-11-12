"""共享枚举：归一状态、映射匹配类型、停滞等级/处置、服务等级（前端 constants/enums.ts 同步一份）。"""
from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    ADMIN = "admin"
    OPS = "ops"
    CLIENT = "client"


class NormalizedStatus(StrEnum):
    CREATED = "created"
    COLLECTED = "collected"
    IN_TRANSIT = "in_transit"
    ARRIVED_HUB = "arrived_hub"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    EXCEPTION = "exception"
    RETURNING = "returning"


NORMALIZED_STATUS_LABELS: dict[str, str] = {
    NormalizedStatus.CREATED.value: "已下单",
    NormalizedStatus.COLLECTED.value: "已揽收",
    NormalizedStatus.IN_TRANSIT.value: "运输中",
    NormalizedStatus.ARRIVED_HUB.value: "到达分拨",
    NormalizedStatus.OUT_FOR_DELIVERY.value: "派送中",
    NormalizedStatus.DELIVERED.value: "已签收",
    NormalizedStatus.EXCEPTION.value: "异常",
    NormalizedStatus.RETURNING.value: "退件",
}

# 正向管道顺序（异常/退件不参与序号比较）
PIPELINE_STATUSES: tuple[str, ...] = (
    NormalizedStatus.CREATED.value,
    NormalizedStatus.COLLECTED.value,
    NormalizedStatus.IN_TRANSIT.value,
    NormalizedStatus.ARRIVED_HUB.value,
    NormalizedStatus.OUT_FOR_DELIVERY.value,
    NormalizedStatus.DELIVERED.value,
)
STAGE_INDEX: dict[str, int] = {status: index for index, status in enumerate(PIPELINE_STATUSES)}

TERMINAL_STATUSES: frozenset[str] = frozenset(
    {NormalizedStatus.DELIVERED.value, NormalizedStatus.RETURNING.value}
)


class MatchType(StrEnum):
    EXACT = "exact"
    ALIAS = "alias"
    FUZZY = "fuzzy"


class AlertSeverity(StrEnum):
    WARN = "warn"
    ALERT = "alert"
    CRITICAL = "critical"


class AlertStatus(StrEnum):
    OPEN = "open"
    CLAIMED = "claimed"
    HANDLED = "handled"
    DISMISSED = "dismissed"


class Disposition(StrEnum):
    CONTACTING = "contacting"
    TRANSFER = "transfer"
    EXCEPTION_CONFIRMED = "exception_confirmed"
    RESEND = "resend"
    DISMISSED = "dismissed"


DISPOSITION_LABELS: dict[str, str] = {
    Disposition.CONTACTING.value: "已联系客户说明",
    Disposition.TRANSFER.value: "转承运商核查",
    Disposition.EXCEPTION_CONFIRMED.value: "确认异常件",
    Disposition.RESEND.value: "安排补发",
    Disposition.DISMISSED.value: "误报关闭",
}


class ServiceLevel(StrEnum):
    STANDARD = "standard"
    EXPRESS = "express"
    BULKY = "bulky"


SERVICE_LEVEL_LABELS: dict[str, str] = {
    ServiceLevel.STANDARD.value: "标准件",
    ServiceLevel.EXPRESS.value: "加急件",
    ServiceLevel.BULKY.value: "大件",
}

REGIONS: tuple[str, ...] = ("华东", "华南", "华北", "华中", "西北", "东北", "西南")
