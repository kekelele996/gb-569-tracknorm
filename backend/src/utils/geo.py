"""线路 key / 数值格式化等跨模块小工具。"""
from __future__ import annotations


def lane_key(origin_region: str, dest_region: str) -> str:
    return f"{origin_region}→{dest_region}"


def round_half_up(value: float, digits: int = 2) -> float:
    factor = 10**digits
    return float(int(value * factor + 0.5)) / factor


def percent(ratio: float, digits: int = 1) -> float:
    return round_half_up(ratio * 100.0, digits)
