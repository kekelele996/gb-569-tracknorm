"""Celery 任务：worker 消费（心跳、周期拉取+归一、周期停滞扫描）。"""
from __future__ import annotations

import time

import redis

from src.config.celery_app import HEARTBEAT_KEY, celery_app
from src.config.settings import settings
from src.utils.logger import get_logger

logger = get_logger("tasks")


def _redis():
    return redis.Redis.from_url(settings.redis_url, decode_responses=True)


@celery_app.task(name="tracknorm.heartbeat")
def heartbeat() -> str:
    try:
        _redis().set(HEARTBEAT_KEY, time.time())
        return "ok"
    except Exception as exc:  # noqa: BLE001
        logger.warning("heartbeat failed: %s", exc)
        return "error"


@celery_app.task(name="tracknorm.pull_and_normalize")
def pull_and_normalize() -> dict:
    """定时任务：拉取轨迹 → 归一 → 停滞扫描（worker 侧，API 默认同步执行同一套 service）。"""
    from src.config.database import session_scope
    from src.services import pull_service, stagnation_engine, track_service

    try:
        with session_scope() as db:
            pull_stats = pull_service.pull_all(db, actor_email="system@tracknorm.io")
            normalize_stats = track_service.normalize_all(db, actor_email="system@tracknorm.io")
            alert_stats = stagnation_engine.detect_and_store(db)
        logger.info(
            "pull_and_normalize done events=%s coverage=%s alerts=%s",
            pull_stats.get("events_fetched"),
            normalize_stats.get("coverage"),
            alert_stats.get("candidates"),
        )
        return {"status": "ok", "coverage": normalize_stats.get("coverage")}
    except Exception as exc:  # noqa: BLE001 - 定时任务失败只记日志
        logger.warning("pull_and_normalize failed: %s", exc)
        return {"status": "error", "message": str(exc)}


@celery_app.task(name="tracknorm.stagnation_scan")
def stagnation_scan() -> dict:
    from src.config.database import session_scope
    from src.services import stagnation_engine

    try:
        with session_scope() as db:
            stats = stagnation_engine.detect_and_store(db)
        return {"status": "ok", "candidates": stats.get("candidates")}
    except Exception as exc:  # noqa: BLE001
        logger.warning("stagnation_scan failed: %s", exc)
        return {"status": "error", "message": str(exc)}
