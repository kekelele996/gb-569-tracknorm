from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base
from src.utils.timeutil import utcnow


class Waybill(Base):
    __tablename__ = "waybills"
    __table_args__ = (
        Index("ix_waybills_lane", "origin_region", "dest_region"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    waybill_no: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    carrier_id: Mapped[int] = mapped_column(ForeignKey("carriers.id"), index=True)
    client_account: Mapped[str] = mapped_column(String(160), index=True)
    client_ref: Mapped[str] = mapped_column(String(48), index=True)
    origin_region: Mapped[str] = mapped_column(String(16))
    dest_region: Mapped[str] = mapped_column(String(16))
    origin_city: Mapped[str] = mapped_column(String(32))
    dest_city: Mapped[str] = mapped_column(String(32))
    service_level: Mapped[str] = mapped_column(String(16), default="standard")
    weight_kg: Mapped[float] = mapped_column(Float, default=1.0)

    # trace_stage：承运商侧最新上报阶段（mock 生成轨迹的唯一依据，归一不修改）
    trace_stage: Mapped[str] = mapped_column(String(24), default="created", index=True)
    # current_status：归一后的当前状态（算法 1 写入）
    current_status: Mapped[str] = mapped_column(String(24), default="created", index=True)

    promised_delivery_at: Mapped[datetime] = mapped_column(DateTime)
    collected_at: Mapped[datetime] = mapped_column(DateTime)
    last_event_at: Mapped[datetime] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
