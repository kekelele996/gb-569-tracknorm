from __future__ import annotations

from pydantic import BaseModel, Field


class PullIn(BaseModel):
    carrier_codes: list[str] | None = None
    force: bool = True


class NormalizeIn(BaseModel):
    version: int | None = Field(default=None, ge=1, le=99)
