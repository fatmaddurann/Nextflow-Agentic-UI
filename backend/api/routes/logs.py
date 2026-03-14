"""
api/routes/logs.py — Log retrieval and WebSocket streaming endpoints.
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.schemas import LogListResponse, LogResponse
from database.crud import count_logs_by_level, get_workflow, get_workflow_logs
from database.database import get_db
from services.log_monitor import ws_manager

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/logs", tags=["Logs"])


@router.get("/{workflow_id}", response_model=LogListResponse, summary="Get workflow logs")
async def get_logs(
    workflow_id: str,
    level: str | None = Query(
        None, description="Filter by level: debug|info|warning|error|critical"
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve paginated log entries for a workflow.
    Supports optional severity level filtering.
    """
    workflow = await get_workflow(db, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found")

    offset = (page - 1) * page_size
    items = await get_workflow_logs(db, workflow_id, level=level, limit=page_size, offset=offset)

    # Total count
    all_items = await get_workflow_logs(db, workflow_id, level=level, limit=100_000, offset=0)

    return LogListResponse(
        workflow_id=workflow_id,
        total=len(all_items),
        items=[LogResponse.model_validate(entry) for entry in items],
    )


@router.get("/{workflow_id}/summary", summary="Log count summary by severity")
async def get_log_summary(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Return count of log entries grouped by severity level."""
    workflow = await get_workflow(db, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found")

    counts = await count_logs_by_level(db, workflow_id)
    return {"workflow_id": workflow_id, "counts": counts}


# WebSocket Real-Time Log Streaming


@router.websocket("/ws/{workflow_id}")
async def websocket_log_stream(websocket: WebSocket, workflow_id: str):
    """
    WebSocket endpoint for real-time log streaming.

    Message types pushed to clients:
    - `log_line`:           A new log line from the pipeline
    - `failure_detected`:   A known failure pattern was detected
    - `ai_analysis_complete`: AI analysis results are ready
    - `status_update`:      Workflow status changed
    """
    await ws_manager.connect(workflow_id, websocket)
    log.info("ws_connected", workflow_id=workflow_id)

    try:
        # Send a welcome message
        await websocket.send_json(
            {
                "type": "connected",
                "workflow_id": workflow_id,
                "message": f"Connected to log stream for workflow {workflow_id}",
            }
        )

        # Keep the connection alive by waiting for client messages or ping/pong
        while True:
            try:
                data = await websocket.receive_json()
                # Handle client-side ping
                if data.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
            except Exception:
                break

    except WebSocketDisconnect:
        log.info("ws_disconnected", workflow_id=workflow_id)
    finally:
        ws_manager.disconnect(workflow_id, websocket)
