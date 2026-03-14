"""
api/routes/containers.py — Docker container management endpoints.
"""

from fastapi import APIRouter, HTTPException, Query

from api.models.schemas import ContainerInfo
from services.container_manager import container_manager

router = APIRouter(prefix="/containers", tags=["Containers"])


@router.get("/", response_model=list[ContainerInfo], summary="List Docker containers")
async def list_containers(
    workflow_id: str | None = Query(None, description="Filter by workflow ID label"),
    all: bool = Query(True, description="Include stopped/exited containers"),
):
    """
    List all Docker containers managed by Nextflow-Agentic-UI.
    Optionally filter by workflow ID label.
    """
    containers = await container_manager.list_containers(
        workflow_id=workflow_id, all_containers=all
    )
    return [ContainerInfo(**c) for c in containers]


@router.get("/{container_id}", response_model=ContainerInfo, summary="Get container details")
async def get_container(container_id: str):
    """Fetch detailed information about a specific container."""
    info = await container_manager.get_container(container_id)
    if not info:
        raise HTTPException(status_code=404, detail=f"Container '{container_id}' not found")
    return ContainerInfo(**info)


@router.get("/{container_id}/logs", response_model=dict, summary="Get container logs")
async def get_container_logs(
    container_id: str,
    tail: int = Query(200, ge=1, le=2000, description="Number of recent log lines to return"),
):
    """Retrieve recent stdout/stderr logs from a Docker container."""
    info = await container_manager.get_container(container_id)
    if not info:
        raise HTTPException(status_code=404, detail=f"Container '{container_id}' not found")

    logs = await container_manager.get_container_logs(container_id, tail=tail)
    return {"container_id": container_id, "logs": logs}


@router.get("/{container_id}/stats", response_model=dict, summary="Get container resource stats")
async def get_container_stats(container_id: str):
    """Return real-time CPU and memory statistics for a running container."""
    stats = await container_manager.get_container_stats(container_id)
    if stats is None:
        raise HTTPException(
            status_code=404, detail=f"Container '{container_id}' not found or not running"
        )
    return {"container_id": container_id, **stats}


@router.post("/{container_id}/restart", response_model=dict, summary="Restart a container")
async def restart_container(container_id: str):
    """Restart a specific Docker container."""
    success = await container_manager.restart_container(container_id)
    if not success:
        raise HTTPException(status_code=400, detail=f"Failed to restart container '{container_id}'")
    return {"message": f"Container {container_id} restarted successfully"}


@router.post("/{container_id}/stop", response_model=dict, summary="Stop a container")
async def stop_container(
    container_id: str,
    timeout: int = Query(30, ge=0, le=300, description="Graceful stop timeout in seconds"),
):
    """Gracefully stop a running Docker container."""
    success = await container_manager.stop_container(container_id, timeout=timeout)
    if not success:
        raise HTTPException(status_code=400, detail=f"Failed to stop container '{container_id}'")
    return {"message": f"Container {container_id} stopped"}


@router.delete("/cleanup", response_model=dict, summary="Prune exited containers")
async def cleanup_containers():
    """Remove all stopped/exited Docker containers to free disk space."""
    count = await container_manager.cleanup_exited_containers()
    return {"message": f"Removed {count} exited containers"}
