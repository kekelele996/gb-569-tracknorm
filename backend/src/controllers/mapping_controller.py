"""映射规则版本控制器。"""
from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from src.middlewares.rbac import Principal
from src.services import audit_service, mapping_service, track_service


def list_versions(db: Session) -> dict:
    active = mapping_service.get_active_version(db)
    return {"versions": mapping_service.list_versions(db), "active_version": active}


def list_rules(db: Session, version: int | None) -> dict:
    return mapping_service.list_rules(db, version)


def evaluate(db: Session, version: int | None) -> dict:
    return track_service.mapping_coverage(db, version)


def create_version(db: Session, base_version: int, note: str | None, principal: Principal, request: Request) -> dict:
    created = mapping_service.create_version(db, base_version, principal.email, note)
    audit_service.record(
        db,
        actor_email=principal.email,
        actor_role=principal.role,
        action="mapping.version.create",
        entity="status_mapping",
        entity_id=created["version"],
        detail={"base_version": base_version, "copied_rules": created["copied_rules"], "added_rules": created["added_rules"]},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return created


def activate(db: Session, version: int, principal: Principal, request: Request) -> dict:
    activated = mapping_service.activate_version(db, version, principal.email)
    audit_service.record(
        db,
        actor_email=principal.email,
        actor_role=principal.role,
        action="mapping.version.activate",
        entity="status_mapping",
        entity_id=version,
        detail={"rules": activated["rules"]},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return activated
