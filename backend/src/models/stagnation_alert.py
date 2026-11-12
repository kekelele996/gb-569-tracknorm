from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base
from src.utils.timeutil import utcnow


class StagnationAlert(Base):
    """停滞预警（算法 2 输出）：线路基线 P50+MAD 的稳健 z 分级 + 处置留痕。"""

    __tablename__ = "stagnation_alerts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    waybill_id: Mapped[int] = mapped_column(ForeignKey("waybills.id"), unique=True, index=True)
    carrier_id: Mapped[int] = mapped_column(ForeignKey("carriers.id"), index=True)
    lane_key: Mapped[str] = mapped_column(String(40), index=True)
    stage: Mapped[str] = mapped_column(String(24))

    baseline_p50_minutes: Mapped[float] = mapped_column(Float, default=0.0)
    baseline_mad_minutes: Mapped[float] = mapped_column(Float, default=0.0)
    baseline_samples: Mapped[int] = mapped_column(Integer, default=0)
    dwell_minutes: Mapped[float] = mapped_column(Float, default=0.0)
    robust_z: Mapped[float] = mapped_column(Float, default=0.0)
    severity: Mapped[str] = mapped_column(String(16), index=True)

    predicted_delivery_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    promised_delivery_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deviation_hours: Mapped[float] = mapped_column(Float, default=0.0)

    status: Mapped[str] = mapped_column(String(16), default="open", index=True)
    claimed_by: Mapped[str | None] = mapped_column(String(160), nullable=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    disposition: Mapped[str | None] = mapped_column(String(32), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    handled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
