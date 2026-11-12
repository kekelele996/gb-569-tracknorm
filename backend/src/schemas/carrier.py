from __future__ import annotations

from pydantic import BaseModel, Field


class CarrierUpdateIn(BaseModel):
    daily_quota: int | None = Field(default=None, ge=0, le=2_000_000)
    rate_limit_per_min: int | None = Field(default=None, ge=1, le=6000)
    is_active: bool | None = None
    note: str | None = Field(default=None, max_length=255)


class CarrierOut(BaseModel):
    id: int
    code: str
    name: str
    status_code_system: str
    api_base: str
    daily_quota: int
    rate_limit_per_min: int
    avg_latency_ms: float
    is_active: bool
    note: str | None
    last_pull_at: str | None
    last_pull_stats: dict
