"""承运商配置控制器。"""
from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from src.services import audit_service, carrier_service


def list_carriers(db: Session) -> list[dict]:
    return carrier_service.list_carriers(db)


def update_carrier(db: Session, carrier_id: int, payload: dict, actor_email: str, actor_role: str, request: Request) -> dict:
    carrier = carrier_service.update_carrier(db, carrier_id, payload)
    audit_service.record(
        db,
        actor_email=actor_email,
        actor_role=actor_role,
        action="carrier.update",
        entity="carrier",
        entity_id=carrier.id,
        detail={key: value for key, value in payload.items() if value is not None},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return carrier_service.serialize(carrier)
