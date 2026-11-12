"""Celery 入口：backend 投递任务，worker 消费（beat 写心跳 + 周期拉取/停滞扫描）。"""
from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from src.config.settings import settings

celery_app = Celery(
    settings.app_name,
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["src.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    enable_utc=False,
    task_track_started=True,
    result_expires=3600,
    broker_connection_retry_on_startup=True,
    worker_hijack_root_logger=False,
)

celery_app.conf.beat_schedule = {
    "tracknorm-heartbeat": {"task": "tracknorm.heartbeat", "schedule": 20.0},
    "tracknorm-pull-cycle": {"task": "tracknorm.pull_and_normalize", "schedule": crontab(minute="*/30")},
    "tracknorm-stagnation-scan": {"task": "tracknorm.stagnation_scan", "schedule": crontab(minute="*/15")},
}

TASK_HEARTBEAT = "tracknorm.heartbeat"
TASK_PULL = "tracknorm.pull_and_normalize"
TASK_STAGNATION = "tracknorm.stagnation_scan"
HEARTBEAT_KEY = f"{settings.brand}:worker:heartbeat"
