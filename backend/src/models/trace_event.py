from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base
from src.utils.timeutil import utcnow


class TraceEvent(Base):
    """承运商原始轨迹事件（未翻译的原始状态码 + 承运商序号）。"""

    __tablename__ = "trace_events"
    __table_args__ = (
        UniqueConstraint("waybill_id", "carrier_event_id", name="uq_trace_waybill_event"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    waybill_id: Mapped[int] = mapped_column(ForeignKey("waybills.id"), index=True)
    carrier_id: Mapped[int] = mapped_column(ForeignKey("carriers.id"), index=True)
    carrier_event_id: Mapped[str] = mapped_column(String(64))
    raw_status: Mapped[str] = mapped_column(String(40), index=True)
    seq: Mapped[int] = mapped_column(Integer, default=0)
    event_time: Mapped[datetime] = mapped_column(DateTime, index=True)
    location: Mapped[str] = mapped_column(String(64))
    note: Mapped[str | None] = mapped_column(String(160), nullable=True)
    raw_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    ingested_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
