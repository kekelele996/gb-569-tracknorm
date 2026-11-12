from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ApiError(BaseModel):
    code: str
    message: str
    detail: Any | None = None


class HealthOut(BaseModel):
    status: str
    db: bool
    redis: bool
    service: str


class RunOut(BaseModel):
    ok: bool = True
    message: str | None = None
    stats: dict[str, Any] = {}
