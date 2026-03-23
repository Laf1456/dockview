"""
Schema API — column-level introspection.
"""

from fastapi import APIRouter, Request, HTTPException

from app.adapters.registry import AdapterRegistry
from app.services import credential_cache

router = APIRouter(tags=["schema"])


@router.get("/databases/{db_id}/schemas/{schema}/tables/{table}/columns")
async def get_columns(db_id: str, schema: str, table: str, request: Request):
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
        cols = await adapter.get_columns(schema, table)
        return [c.model_dump() for c in cols]
    except Exception as e:
        raise HTTPException(500, str(e))
