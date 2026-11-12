from __future__ import annotations

from pydantic import BaseModel


class WaybillOut(BaseModel):
    id: int
    waybill_no: str
    carrier_code: str
    carrier_name: str
    client_account: str
    client_ref: str
    lane: str
    origin_city: str
    dest_city: str
    service_level: str
    weight_kg: float
    current_status: str
    trace_stage: str
    promised_delivery_at: str | None
    last_event_at: str | None
    coverage: float
    conflict_count: int


class BucketOut(BaseModel):
    status: str
    label: str
    count: int


class WaybillListOut(BaseModel):
    items: list[WaybillOut]
    total: int
    page: int
    size: int
    buckets: list[BucketOut]


class WaybillEventOut(BaseModel):
    carrier_event_id: str
    raw_status: str
    seq: int
    event_time: str | None
    location: str
    note: str | None


class WaybillDetailOut(BaseModel):
    waybill: WaybillOut
    events: list[WaybillEventOut]
    normalized_events: list[dict]
    mapping_hits: list[dict]
    conflicts: list[dict]
    coverage: float
    mapping_version: int
    duplicate_count: int
    disorder_count: int
    unmapped_count: int
    alert: dict | None = None
