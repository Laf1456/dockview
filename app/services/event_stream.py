"""
Server-Sent Events for live container/DB status updates.
"""

import asyncio
import json
import logging

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

logger = logging.getLogger("dockview.sse")

router = APIRouter(tags=["events"])


@router.get("/events")
async def event_stream(request: Request):
    """SSE endpoint — push DB list updates to the browser."""

    async def generator():
        inspector = request.app.state.inspector
        last_count = -1
        last_statuses: dict[str, str] = {}

        # ✅ Send initial state immediately (prevents UI hanging)
        dbs = inspector.get_all_databases()
        payload = {
            "type": "init",
            "count": len(dbs),
            "databases": [
                {
                    "id": d.id,
                    "name": d.name,
                    "type": d.type.value,
                    "status": d.status,
                }
                for d in dbs
            ],
        }
        yield f"data: {json.dumps(payload)}\n\n"
        last_count = len(dbs)
        last_statuses = {d.id: d.status for d in dbs}

        while True:
            # ✅ stop if client disconnects
            if await request.is_disconnected():
                logger.debug("SSE client disconnected")
                break

            dbs = inspector.get_all_databases()
            current_statuses = {d.id: d.status for d in dbs}

            # ✅ Only send updates when something changes
            if len(dbs) != last_count or current_statuses != last_statuses:
                payload = {
                    "type": "update",
                    "count": len(dbs),
                    "databases": [
                        {
                            "id": d.id,
                            "name": d.name,
                            "type": d.type.value,
                            "status": d.status,
                        }
                        for d in dbs
                    ],
                }
                yield f"data: {json.dumps(payload)}\n\n"

                last_count = len(dbs)
                last_statuses = current_statuses

            else:
                # ✅ Heartbeat (keeps connection alive, prevents reconnect loop)
                yield f": ping\n\n"

            await asyncio.sleep(2)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            # ✅ Required for SSE stability
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # for nginx
        },
    )