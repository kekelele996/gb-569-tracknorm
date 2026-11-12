from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base
from src.utils.timeutil import utcnow


class NormalizedTrack(Base):
    """归一轨迹（算法 1 输出）：排序去重后的轨迹、当前状态、覆盖率与冲突明细。"""

    __tablename__ = "normalized_tracks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    waybill_id: Mapped[int] = mapped_column(ForeignKey("waybills.id"), unique=True, index=True)
    mapping_version: Mapped[int] = mapped_column(Integer, default=1)
    current_status: Mapped[str] = mapped_column(String(24), index=True)
    normalized_events: Mapped[list] = mapped_column(JSON, default=list)
    mapping_hits: Mapped[list] = mapped_column(JSON, default=list)
    conflicts: Mapped[list] = mapped_column(JSON, default=list)
    event_count: Mapped[int] = mapped_column(Integer, default=0)
    mapped_count: Mapped[int] = mapped_column(Integer, default=0)
    unmapped_count: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_count: Mapped[int] = mapped_column(Integer, default=0)
    disorder_count: Mapped[int] = mapped_column(Integer, default=0)
    conflict_count: Mapped[int] = mapped_column(Integer, default=0)
    coverage: Mapped[float] = mapped_column(Float, default=0.0)
    last_event_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
