from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base
from src.utils.timeutil import utcnow


class StatusMapping(Base):
    """状态映射规则（按版本管理，v2 由主流程创建）。"""

    __tablename__ = "status_mappings"
    __table_args__ = (
        UniqueConstraint("version", "carrier_code", "source_status", name="uq_mapping_version_source"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    version: Mapped[int] = mapped_column(Integer, index=True)
    carrier_code: Mapped[str] = mapped_column(String(24), default="*")
    source_status: Mapped[str] = mapped_column(String(40), index=True)
    target_status: Mapped[str] = mapped_column(String(24), index=True)
    match_type: Mapped[str] = mapped_column(String(16), default="exact")
    score: Mapped[float] = mapped_column(Float, default=1.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(160), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
