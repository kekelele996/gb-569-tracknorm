"""ORM 模型聚合导出（Base 用于 create_all）。"""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


from src.models.audit import AuditLog  # noqa: E402
from src.models.user import User  # noqa: E402
from src.models.carrier import Carrier  # noqa: E402
from src.models.waybill import Waybill  # noqa: E402
from src.models.trace_event import TraceEvent  # noqa: E402
from src.models.status_mapping import StatusMapping  # noqa: E402
from src.models.normalized_track import NormalizedTrack  # noqa: E402
from src.models.stagnation_alert import StagnationAlert  # noqa: E402

__all__ = [
    "Base",
    "AuditLog",
    "User",
    "Carrier",
    "Waybill",
    "TraceEvent",
    "StatusMapping",
    "NormalizedTrack",
    "StagnationAlert",
]
