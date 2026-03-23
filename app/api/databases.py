"""
Databases API — list, connect, browse.
"""

import logging
from fastapi import APIRouter, Request, HTTPException, Body
from fastapi.responses import JSONResponse

from app.models import DatabaseMeta, CredentialInput, DB_DISPLAY_NAMES, DB_ICONS, DB_COLORS
from app.adapters.registry import AdapterRegistry
from app.services import credential_cache

logger = logging.getLogger("dockview.api.databases")

router = APIRouter(tags=["databases"])


def _to_meta(db) -> dict:
    return {
        "id": db.id,
        "name": db.name,
        "type": db.type.value,
        "display_name": DB_DISPLAY_NAMES.get(db.type, db.type.value),
        "icon": DB_ICONS.get(db.type, "🗄️"),
        "color": DB_COLORS.get(db.type, "#888"),
        "status": db.status,
        "host": db.host,
        "port": db.port,
        "container_name": db.container_name,
        "image": db.image,
    }


@router.get("/databases")
async def list_databases(request: Request):
    inspector = request.app.state.inspector
    if not inspector.is_connected:
        return JSONResponse(
            {"error": "Docker not available", "detail": inspector.error},
            status_code=503,
        )
    dbs = inspector.get_all_databases()
    return [_to_meta(d) for d in dbs]


@router.get("/databases/{db_id}")
async def get_database(db_id: str, request: Request):
    inspector = request.app.state.inspector
    db = inspector.get_database(db_id)
    if not db:
        raise HTTPException(404, "Database not found")
    return _to_meta(db)


@router.post("/databases/{db_id}/connect")
async def test_connection(db_id: str, request: Request, creds: CredentialInput | None = None):
    inspector = request.app.state.inspector
    db = inspector.get_database(db_id)
    if not db:
        raise HTTPException(404, "Database not found")

    override = {}
    if creds:
        if creds.user:
            override["user"] = creds.user
        if creds.password:
            override["password"] = creds.password
        if creds.database:
            override["database"] = creds.database

    if override:
        credential_cache.set_creds(db_id, override)

    AdapterClass = AdapterRegistry.get(db.type)
    if not AdapterClass:
        raise HTTPException(400, f"No adapter for {db.type.value}")

    cached = credential_cache.get(db_id)
    adapter = AdapterClass(db, credential_override=cached)
    ok = await adapter.test_connection()

    return {"connected": ok, "db_id": db_id}


@router.get("/databases/{db_id}/schemas")
async def list_schemas(db_id: str, request: Request):
    inspector = request.app.state.inspector
    db = inspector.get_database(db_id)
    if not db:
        raise HTTPException(404, "Database not found")

    AdapterClass = AdapterRegistry.get(db.type)
    if not AdapterClass:
        raise HTTPException(400, f"No adapter for {db.type.value}")

    cached = credential_cache.get(db_id)
    adapter = AdapterClass(db, credential_override=cached)

    try:
        schemas = await adapter.list_databases()
        return schemas
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/databases/{db_id}/schemas/{schema}/tables")
async def list_tables(db_id: str, schema: str, request: Request):
    inspector = request.app.state.inspector
    db = inspector.get_database(db_id)
    if not db:
        raise HTTPException(404, "Database not found")

    AdapterClass = AdapterRegistry.get(db.type)
    if not AdapterClass:
        raise HTTPException(400, f"No adapter for {db.type.value}")

    cached = credential_cache.get(db_id)
    adapter = AdapterClass(db, credential_override=cached)

    try:
        tables = await adapter.list_tables(schema)
        return [t.model_dump() for t in tables]
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/databases/{db_id}/schemas/{schema}/tables/{table}/preview")
async def preview_table(
    db_id: str,
    schema: str,
    table: str,
    request: Request,
    limit: int = 50,
    offset: int = 0,
):
    inspector = request.app.state.inspector
    db = inspector.get_database(db_id)
    if not db:
        raise HTTPException(404, "Database not found")

    AdapterClass = AdapterRegistry.get(db.type)
    if not AdapterClass:
        raise HTTPException(400, f"No adapter for {db.type.value}")

    cached = credential_cache.get(db_id)
    adapter = AdapterClass(db, credential_override=cached)

    try:
        preview = await adapter.preview_table(schema, table, limit=limit, offset=offset)
        return preview.model_dump()
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/databases/{db_id}/info")
async def server_info(db_id: str, request: Request):
    inspector = request.app.state.inspector
    db = inspector.get_database(db_id)
    if not db:
        raise HTTPException(404, "Database not found")

    AdapterClass = AdapterRegistry.get(db.type)
    if not AdapterClass:
        raise HTTPException(400, f"No adapter for {db.type.value}")

    cached = credential_cache.get(db_id)
    adapter = AdapterClass(db, credential_override=cached)

    try:
        return await adapter.get_server_info()
    except Exception as e:
        raise HTTPException(500, str(e))
