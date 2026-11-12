from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base
from src.utils.timeutil import utcnow


class Carrier(Base):
    __tablename__ = "carriers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(60))
    status_code_system: Mapped[str] = mapped_column(String(80))
    api_base: Mapped[str] = mapped_column(String(160))
    daily_quota: Mapped[int] = mapped_column(Integer, default=10000)
    rate_limit_per_min: Mapped[int] = mapped_column(Integer, default=60)
    avg_latency_ms: Mapped[float] = mapped_column(Float, default=180.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_pull_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_pull_stats: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
