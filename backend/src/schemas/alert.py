from __future__ import annotations

from pydantic import BaseModel, Field


class ClaimIn(BaseModel):
    note: str | None = Field(default=None, max_length=400)


class DisposeIn(BaseModel):
    disposition: str = Field(min_length=2, max_length=32)
    note: str | None = Field(default=None, max_length=400)
