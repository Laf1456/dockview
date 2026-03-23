"""
Containers API — list raw Docker containers.
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(tags=["containers"])


@router.get("/containers/status")
async def docker_status(request: Request):
    inspector = request.app.state.inspector
    return {
        "connected": inspector.is_connected,
        "error": inspector.error,
        "db_count": len(inspector.get_all_databases()),
    }


@router.post("/containers/refresh")
async def refresh(request: Request):
    inspector = request.app.state.inspector
    await inspector.refresh()
    return {"ok": True, "count": len(inspector.get_all_databases())}
