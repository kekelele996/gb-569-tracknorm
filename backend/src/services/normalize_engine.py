"""算法 1：承运商轨迹归一与乱序修复（纯函数，可单测可复现）。

口径（README / TESTING 同步）：
1. 稳定排序：按 (event_time, seq, carrier_event_id) 升序 —— 修复乱序到达；
2. 窗口去重：同 target_status + 同 location 且与上一条保留事件的间隔 ≤ 30 分钟 → 判重复回推丢弃；
3. 状态机校验：只允许「前向或同阶段」推进（异常/退件另有规则），回退事件标 conflict 且不改变当前状态；
4. 映射打分：精确 1.0 / 别名 0.8 / 模糊 0.5–0.7 / 未命中 0（<0.5 视为未命中），取最高分规则；
   覆盖率 = 命中映射事件数 / 原始事件总数。

输出：归一轨迹（时间轴）、当前状态、覆盖率、冲突/重复/乱序/未命中明细。
"""
from __future__ import annotations

from datetime import timedelta
from difflib import SequenceMatcher

from src.constants.enums import (
    MatchType,
    NormalizedStatus,
    PIPELINE_STATUSES,
    STAGE_INDEX,
)
from src.constants.limits import (
    ALIAS_SCORE,
    DEDUPE_WINDOW_MINUTES,
    EXACT_SCORE,
    FUZZY_MAX_SCORE,
    FUZZY_MIN_SCORE,
    MAPPING_MIN_SCORE,
)
from src.utils.timeutil import iso_utc

CONFLICT_REASON_LABELS = {
    "illegal_rollback": "状态回退（非法迁移）",
}

PIPELINE_AFTER_COLLECT = set(PIPELINE_STATUSES[1:])


def normalize_raw_status(raw: str) -> str:
    return "_".join(str(raw).strip().upper().split())


def similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, left, right).ratio()


def transition_legal(previous: str | None, target: str) -> bool:
    """状态机：前向或同阶段合法；回退非法；异常/退件按业务规则特判。"""
    if previous is None:
        return True
    if previous == target:
        return True
    if target == NormalizedStatus.EXCEPTION.value:
        return previous in PIPELINE_AFTER_COLLECT
    if target == NormalizedStatus.RETURNING.value:
        return previous == NormalizedStatus.EXCEPTION.value or STAGE_INDEX.get(previous, 0) >= STAGE_INDEX[
            NormalizedStatus.IN_TRANSIT.value
        ]
    if previous == NormalizedStatus.EXCEPTION.value:
        return target in PIPELINE_AFTER_COLLECT
    if previous == NormalizedStatus.RETURNING.value:
        return False
    return STAGE_INDEX.get(target, -1) >= STAGE_INDEX.get(previous, 99)


def resolve_mapping(raw_status: str, carrier_code: str, rules: list[dict]) -> dict | None:
    """映射打分：精确 1.0 / 别名 0.8 / 模糊 0.5–0.7；取分数最高（同分时承运商专用规则优先）。"""
    normalized = normalize_raw_status(raw_status)
    best: tuple[tuple[float, int], dict] | None = None
    for rule in rules:
        rule_carrier = str(rule.get("carrier_code") or "*")
        if rule_carrier not in ("*", carrier_code):
            continue
        source = normalize_raw_status(rule.get("source_status", ""))
        match_type = rule.get("match_type", MatchType.EXACT.value)
        declared_score = float(rule.get("score") or EXACT_SCORE)
        score: float | None = None

        if normalized == source:
            if match_type == MatchType.EXACT.value:
                score = EXACT_SCORE
            elif match_type == MatchType.ALIAS.value:
                score = ALIAS_SCORE
            else:
                # 人工标定的模糊规则：命中源码表但语义置信度偏低（0.5–0.7）
                score = min(FUZZY_MAX_SCORE, max(FUZZY_MIN_SCORE, declared_score))
        elif match_type == MatchType.FUZZY.value:
            ratio = similarity(normalized, source)
            if ratio >= 0.62:
                score = round(min(FUZZY_MAX_SCORE, FUZZY_MIN_SCORE + 0.2 * ratio), 2)

        if score is None or score < MAPPING_MIN_SCORE:
            continue
        rank = (score, 1 if rule_carrier == carrier_code else 0)
        if best is None or rank > best[0]:
            best = (
                rank,
                {
                    "rule_id": rule.get("id"),
                    "source_status": rule.get("source_status"),
                    "target_status": rule.get("target_status"),
                    "match_type": match_type,
                    "score": round(score, 2),
                    "carrier_code": rule_carrier,
                },
            )
    return best[1] if best else None


def _serialize_event(event: dict, target: dict | None) -> dict:
    payload = {
        "carrier_event_id": event["carrier_event_id"],
        "raw_status": event["raw_status"],
        "seq": event["seq"],
        "event_time": iso_utc(event["event_time"]),
        "location": event["location"],
        "note": event.get("note"),
    }
    if target is not None:
        payload.update(
            {
                "target_status": target["target_status"],
                "match_type": target["match_type"],
                "score": target["score"],
                "rule_id": target["rule_id"],
            }
        )
    return payload


def normalize_waybill(events: list[dict], carrier_code: str, rules: list[dict]) -> dict:
    """对单个运单执行排序 → 映射 → 去重 → 状态机校验，返回归一结果与统计。"""
    event_count = len(events)
    if event_count == 0:
        return {
            "normalized_events": [],
            "mapping_hits": [],
            "duplicates": [],
            "unmapped": [],
            "conflicts": [],
            "event_count": 0,
            "mapped_count": 0,
            "unmapped_count": 0,
            "duplicate_count": 0,
            "disorder_count": 0,
            "conflict_count": 0,
            "coverage": 0.0,
            "current_status": NormalizedStatus.CREATED.value,
            "last_event_time": None,
        }

    # 乱序指标：按承运商自增 seq 的到达顺序，event_time 回退的次数
    by_seq = sorted(events, key=lambda item: (item["seq"], item["carrier_event_id"]))
    disorder_count = sum(
        1 for index in range(1, len(by_seq)) if by_seq[index]["event_time"] < by_seq[index - 1]["event_time"]
    )

    # 1) 稳定排序修复乱序
    time_ordered = sorted(events, key=lambda item: (item["event_time"], item["seq"], item["carrier_event_id"]))

    # 2) 映射打分
    mapped: list[dict] = []
    unmapped: list[dict] = []
    for event in time_ordered:
        hit = resolve_mapping(event["raw_status"], carrier_code, rules)
        if hit is None:
            unmapped.append(_serialize_event(event, None))
            continue
        mapped.append({**event, "target_status": hit["target_status"], "match_type": hit["match_type"],
                       "score": hit["score"], "rule_id": hit["rule_id"]})

    kept: list[dict] = []
    duplicates: list[dict] = []
    conflicts: list[dict] = []
    current_status: str | None = None
    window = timedelta(minutes=DEDUPE_WINDOW_MINUTES)

    for event in mapped:
        # 3) 窗口去重（同状态同地点 30 分钟内重复回推）
        if kept:
            last = kept[-1]
            if (
                last["target_status"] == event["target_status"]
                and last["location"] == event["location"]
                and (event["event_time"] - last["event_time"]) <= window
            ):
                duplicates.append(_serialize_event(event, event))
                continue
        # 4) 状态机合法迁移校验
        if current_status is not None and not transition_legal(current_status, event["target_status"]):
            conflicts.append(
                {
                    **_serialize_event(event, event),
                    "from_status": current_status,
                    "to_status": event["target_status"],
                    "reason": "illegal_rollback",
                    "reason_label": CONFLICT_REASON_LABELS["illegal_rollback"],
                }
            )
            continue
        current_status = event["target_status"]
        kept.append(event)

    # 映射命中聚合（规则维度，映射规则页展示）
    hit_index: dict[int | None, dict] = {}
    for event in mapped:
        key = event["rule_id"]
        entry = hit_index.setdefault(
            key,
            {
                "rule_id": key,
                "source_status": event["raw_status"],
                "target_status": event["target_status"],
                "match_type": event["match_type"],
                "score": event["score"],
                "hits": 0,
                "conflicts": 0,
            },
        )
        entry["hits"] += 1
    for conflict in conflicts:
        for entry in hit_index.values():
            if entry["source_status"] == conflict["raw_status"] and entry["target_status"] == conflict["to_status"]:
                entry["conflicts"] += 1
                break

    mapped_count = len(mapped)
    return {
        "normalized_events": [_serialize_event(event, event) for event in kept],
        "mapping_hits": list(hit_index.values()),
        "duplicates": duplicates,
        "unmapped": unmapped,
        "conflicts": conflicts,
        "event_count": event_count,
        "mapped_count": mapped_count,
        "unmapped_count": len(unmapped),
        "duplicate_count": len(duplicates),
        "disorder_count": disorder_count,
        "conflict_count": len(conflicts),
        "coverage": round(mapped_count / event_count, 4),
        "current_status": current_status or NormalizedStatus.CREATED.value,
        "last_event_time": kept[-1]["event_time"] if kept else None,
    }
