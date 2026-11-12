"""路由聚合：统一 /api 前缀（Nginx 反代时剥掉 /api）。"""
from fastapi import APIRouter

from src.routes.alerts import router as alerts_router
from src.routes.auth import router as auth_router
from src.routes.carriers import router as carriers_router
from src.routes.health import router as health_router
from src.routes.mappings import router as mappings_router
from src.routes.reports import router as reports_router
from src.routes.tracks import router as tracks_router
from src.routes.waybills import router as waybills_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(carriers_router)
api_router.include_router(waybills_router)
api_router.include_router(tracks_router)
api_router.include_router(mappings_router)
api_router.include_router(alerts_router)
api_router.include_router(reports_router)
