from fastapi import APIRouter

from app.api.routes.v1 import (
    alerts,
    auth,
    dashboard,
    devices,
    incidents,
    intersections,
    violations,
    websocket,
)


router = APIRouter(prefix="/api/v1")
router.include_router(auth.router)
router.include_router(intersections.router)
router.include_router(incidents.router)
router.include_router(violations.router)
router.include_router(alerts.router)
router.include_router(devices.router)
router.include_router(dashboard.router)
router.include_router(websocket.router)
