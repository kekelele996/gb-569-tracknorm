from __future__ import annotations

from pydantic import BaseModel, Field


class MappingIn(BaseModel):
    id: int | None = None
    carrier_code: str
    source_status: str
    target_status: str
    match_type: str
    score: float = 1.0
    note: str | None = None


class CreateVersionIn(BaseModel):
    base_version: int = Field(default=1, ge=1, le=99)
    note: str | None = Field(default=None, max_length=255)


class ActivateVersionIn(BaseModel):
    version: int = Field(ge=1, le=99)
