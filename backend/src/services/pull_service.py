"""拉取承运商轨迹（内置 mock，含 429 限流退避）+ 幂等入库 + 拉取统计。"""
from __future__ import annotations

import time
from collections import defaultdict
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.constants.limits import PULL_BUCKET_KEY
from src.models.carrier import Carrier
from src.models.trace_event import TraceEvent
from src.models.waybill import Waybill
from src.services import audit_service
from src.services.carrier_mock import CarrierRateLimited, MockCarrierClient
from src.utils.logger import get_logger
from src.utils.timeutil import iso_utc, utcnow

logger = get_logger("pull")
LAST_PULL_KEY = f"{settings.brand}:last_pull"


def _redis():
    try:
        import redis

        return redis.Redis.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=2)
    except Exception:  # noqa: BLE001
        return None


def _chunked(items: list, size: int) -> list[list]:
    return [items[index: index + size] for index in range(0, len(items), size)]


def pull_all(
    db: Session,
    actor_email: str,
    carrier_codes: list[str] | None = None,
    ip: str | None = None,
) -> dict:
    """对 3 家承运商拉取全部运单轨迹：前 2 次批量调用返回 429 → 退避重试。"""
    started = time.time()
    carriers_query = select(Carrier).order_by(Carrier.id)
    if carrier_codes:
        carriers_query = carriers_query.where(Carrier.code.in_(carrier_codes))
    carriers = db.scalars(carriers_query).all()
    if not carriers:
        return {"waybills": 0, "events_fetched": 0, "rate_limit_hits": 0, "carriers": []}

    client = MockCarrierClient(rate_limit_budget=settings.mock_429_budget)
    backoff_ms: list[int] = []
    total_waybills = 0
    total_fetched = 0
    total_inserted = 0
    total_unchanged = 0
    per_carrier: list[dict] = []

    for carrier in carriers:
        waybills = db.scalars(
            select(Waybill).where(Waybill.carrier_id == carrier.id).order_by(Waybill.id)
        ).all()
        carrier_events = 0
        carrier_inserted = 0
        for batch in _chunked(list(waybills), max(10, settings.pull_batch_size)):
            attempts = 0
            while True:
                try:
                    payload = client.fetch_batch(carrier, batch)
                    break
                except CarrierRateLimited as exc:
                    backoff_ms.append(exc.retry_after_ms)
                    logger.warning(
                        "mock carrier 429 carrier=%s attempt=%s backoff_ms=%s",
                        exc.carrier_code,
                        exc.hit_index,
                        exc.retry_after_ms,
                    )
                    time.sleep(exc.retry_after_ms / 1000.0)
                    attempts += 1
                    if attempts > 6:  # pragma: no cover - mock 不会一直限流
                        raise
            batch_ids = [waybill.id for waybill in batch]
            existing = set(
                db.execute(
                    select(TraceEvent.waybill_id, TraceEvent.carrier_event_id).where(
                        TraceEvent.waybill_id.in_(batch_ids)
                    )
                ).all()
            )
            waybill_index = {waybill.waybill_no: waybill for waybill in batch}
            for item in payload:
                waybill = waybill_index[item["waybill_no"]]
                carrier_events += 1
                key = (waybill.id, item["carrier_event_id"])
                if key in existing:
                    total_unchanged += 1
                    continue
                db.add(
                    TraceEvent(
                        waybill_id=waybill.id,
                        carrier_id=carrier.id,
                        carrier_event_id=item["carrier_event_id"],
                        raw_status=item["raw_status"],
                        seq=item["seq"],
                        event_time=item["event_time"],
                        location=item["location"],
                        note=item["note"],
                        raw_payload=item["raw_payload"],
                    )
                )
                existing.add(key)
                carrier_inserted += 1
                total_inserted += 1
            total_fetched += len(payload)

        pulled_at = utcnow()
        carrier.last_pull_at = pulled_at
        carrier.last_pull_stats = {
            "events": carrier_events,
            "waybills": len(waybills),
            "inserted": carrier_inserted,
            "rate_limit_hits": client.hits,
            "pulled_at": iso_utc(pulled_at),
        }
        total_waybills += len(waybills)
        per_carrier.append(
            {
                "carrier_code": carrier.code,
                "carrier_name": carrier.name,
                "waybills": len(waybills),
                "events_fetched": carrier_events,
                "inserted": carrier_inserted,
                "last_pull_at": iso_utc(pulled_at),
            }
        )

    db.flush()
    duration_ms = int((time.time() - started) * 1000)
    stats = {
        "waybills": total_waybills,
        "carriers": per_carrier,
        "events_fetched": total_fetched,
        "events_inserted": total_inserted,
        "events_unchanged": total_unchanged,
        "rate_limit_hits": client.hits,
        "backoff_ms": backoff_ms,
        "duration_ms": duration_ms,
        "pulled_at": iso_utc(utcnow()),
        "mock_boundary": "mock 只返回标准码表事件；重复回推/乱序/非法回退/未知码为 seed 注入的历史脏数据",
    }
    audit_service.record(
        db,
        actor_email=actor_email,
        actor_role="",
        action="track.pull",
        entity="carrier",
        entity_id=",".join(carrier.code for carrier in carriers),
        detail={
            "waybills": total_waybills,
            "events_fetched": total_fetched,
            "rate_limit_hits": client.hits,
            "backoff_ms": backoff_ms,
        },
        ip=ip,
    )
    redis_client = _redis()
    if redis_client is not None:
        try:
            import json

            redis_client.set(LAST_PULL_KEY, json.dumps(stats, ensure_ascii=False, default=str), ex=86400)
        except Exception:  # noqa: BLE001
            pass
    return stats


def last_pull_stats() -> dict | None:
    redis_client = _redis()
    if redis_client is None:
        return None
    try:
        import json

        value = redis_client.get(LAST_PULL_KEY)
        return json.loads(value) if value else None
    except Exception:  # noqa: BLE001
        return None
