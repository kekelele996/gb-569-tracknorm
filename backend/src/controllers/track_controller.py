"""轨迹拉取 / 归一控制器。"""
from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from src.middlewares.rbac import Principal
from src.services import pull_service, track_service


def pull(
    db: Session,
    principal: Principal,
    request: Request,
    carrier_codes: list[str] | None,
    force: bool,
) -> dict:
    stats = pull_service.pull_all(
        db,
        actor_email=principal.email,
        carrier_codes=carrier_codes,
        ip=request.client.host if request.client else None,
    )
    db.commit()
    stats["forced"] = force
    return stats


def normalize(db: Session, principal: Principal, request: Request, version: int | None) -> dict:
    from src.services import stagnation_engine

    stats = track_service.normalize_all(
        db,
        actor_email=principal.email,
        version=version,
        ip=request.client.host if request.client else None,
    )
    stagnation_stats = stagnation_engine.detect_and_store(db)
    db.commit()
    stats["stagnation"] = stagnation_stats
    track_service.cache_extra({"stagnation": stagnation_stats})
    return stats


def last_runs(db: Session) -> dict:
    return {
        "pull": pull_service.last_pull_stats(),
        "normalize": track_service.last_normalize_stats(),
    }
