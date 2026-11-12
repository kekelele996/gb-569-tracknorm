from __future__ import annotations

from pydantic import BaseModel


class CarrierQualityOut(BaseModel):
    carrier_code: str
    carrier_name: str
    waybills: int
    events: int
    mapped_events: int
    unmapped_events: int
    duplicate_events: int
    disorder_events: int
    conflict_events: int
    coverage: float
    quality_score: float
    rate_limit_hits: int
