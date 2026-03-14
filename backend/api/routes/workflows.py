"""
api/routes/workflows.py — Workflow management endpoints.
"""

import hashlib
import os
from pathlib import Path

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.schemas import (
    AIAnalysisResponse,
    FileUploadResponse,
    WorkflowCreateRequest,
    WorkflowListResponse,
    WorkflowResponse,
)
from database.crud import (
    delete_workflow,
    get_dashboard_summary,
    get_latest_analysis,
    get_workflow,
    list_workflows,
)
from database.database import get_db
from services.ai_agent import ai_agent
from services.log_monitor import log_monitor
from services.workflow_manager import workflow_manager

router = APIRouter(prefix="/workflows", tags=["Workflows"])

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "/tmp/nf_uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# CRUD Endpoints


@router.post(
    "/",
    response_model=WorkflowResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start a new pipeline run",
)
async def start_workflow(
    body: WorkflowCreateRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Launch a new Nextflow pipeline run.
    The pipeline runs asynchronously; poll `/workflows/{workflow_id}` for status.
    """
    params = {
        k: v
        for k, v in {
            "reads": body.reads,
            "genome": body.genome,
            "gtf": body.gtf,
            "star_index": body.star_index,
            **body.extra_params,
        }.items()
        if v is not None
    }

    workflow_id = await workflow_manager.start_pipeline(
        name=body.name,
        pipeline_type=body.pipeline_type,
        profile=body.profile,
        params=params,
        owner=body.owner or "anonymous",
        project_name=body.project_name,
        description=body.description,
    )

    # Start log monitoring in background
    log_file = Path(os.getenv("NEXTFLOW_LOG_DIR", "/pipeline/logs")) / f"{workflow_id}.log"
    background_tasks.add_task(log_monitor.start_monitoring, workflow_id, str(log_file))

    # Fetch and return the created record
    workflow = await get_workflow(db, workflow_id)
    if not workflow:
        raise HTTPException(status_code=500, detail="Workflow creation failed")
    return WorkflowResponse.model_validate(workflow)


@router.get("/", response_model=WorkflowListResponse, summary="List all workflow runs")
async def list_workflow_runs(
    status_filter: str | None = Query(
        None,
        alias="status",
        description="Filter by status: pending|running|completed|failed|cancelled",
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Return a paginated list of all pipeline runs."""
    offset = (page - 1) * page_size
    items = await list_workflows(db, status=status_filter, limit=page_size, offset=offset)
    # Simple total count via a separate call (production would use COUNT query)
    all_items = await list_workflows(db, status=status_filter, limit=10_000, offset=0)
    return WorkflowListResponse(
        total=len(all_items),
        page=page,
        page_size=page_size,
        items=[WorkflowResponse.model_validate(w) for w in items],
    )


@router.get("/active", response_model=list[str], summary="List active workflow IDs")
async def list_active_workflows():
    """Return workflow IDs of currently executing pipelines."""
    return workflow_manager.list_active()


@router.get("/dashboard", summary="Dashboard summary statistics")
async def get_dashboard(db: AsyncSession = Depends(get_db)):
    """Return aggregate statistics for the UI dashboard."""
    return await get_dashboard_summary(db)


@router.get("/{workflow_id}", response_model=WorkflowResponse, summary="Get workflow details")
async def get_workflow_run(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Fetch full details of a workflow run by ID."""
    workflow = await get_workflow(db, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found")
    return WorkflowResponse.model_validate(workflow)


@router.delete(
    "/{workflow_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancel and delete a workflow run",
)
async def cancel_workflow(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Stop a running workflow and remove its database record.
    Note: Work directory files are NOT deleted automatically.
    """
    # Stop if running
    await workflow_manager.stop_pipeline(workflow_id)

    deleted = await delete_workflow(db, workflow_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found")


@router.post(
    "/{workflow_id}/stop", response_model=WorkflowResponse, summary="Stop a running workflow"
)
async def stop_workflow(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Gracefully terminate a running pipeline process."""
    stopped = await workflow_manager.stop_pipeline(workflow_id)
    if not stopped:
        raise HTTPException(
            status_code=404, detail=f"Workflow '{workflow_id}' is not currently running"
        )
    workflow = await get_workflow(db, workflow_id)
    return WorkflowResponse.model_validate(workflow)


@router.post(
    "/{workflow_id}/resume", response_model=WorkflowResponse, summary="Resume a failed workflow"
)
async def resume_workflow(
    workflow_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Resume a previously failed or cancelled pipeline using Nextflow's -resume flag.
    Reuses the existing work cache directory to skip already-completed steps.
    """
    new_id = await workflow_manager.resume_pipeline(workflow_id)
    if not new_id:
        raise HTTPException(status_code=404, detail=f"Original workflow '{workflow_id}' not found")

    log_file = Path(os.getenv("NEXTFLOW_LOG_DIR", "/pipeline/logs")) / f"{new_id}.log"
    background_tasks.add_task(log_monitor.start_monitoring, new_id, str(log_file))

    workflow = await get_workflow(db, new_id)
    return WorkflowResponse.model_validate(workflow)


# AI Analysis Endpoints


@router.get(
    "/{workflow_id}/analysis",
    response_model=AIAnalysisResponse,
    summary="Get AI analysis for a workflow",
)
async def get_ai_analysis(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve the latest AI-generated troubleshooting analysis for a workflow.
    Analysis is automatically triggered when failures are detected.
    """
    analysis = await get_latest_analysis(db, workflow_id)
    if not analysis:
        raise HTTPException(
            status_code=404, detail="No AI analysis available for this workflow yet"
        )
    return AIAnalysisResponse.model_validate(analysis)


@router.post("/{workflow_id}/analyze", response_model=dict, summary="Manually trigger AI analysis")
async def trigger_ai_analysis(
    workflow_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Manually trigger AI analysis on any workflow (even non-failed ones).
    Runs asynchronously; check `/workflows/{workflow_id}/analysis` for results.
    """
    workflow = await get_workflow(db, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found")

    background_tasks.add_task(
        ai_agent.analyze_workflow,
        workflow_id=workflow_id,
    )
    return {"message": "AI analysis triggered", "workflow_id": workflow_id}


# File Upload Endpoint


@router.post(
    "/upload",
    response_model=FileUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload input FASTQ files",
)
async def upload_input_file(
    file: UploadFile = File(..., description="FASTQ file (.fastq, .fastq.gz, .fq, .fq.gz)"),
    project: str = Form("default", description="Project name for organisation"),
):
    """
    Upload a FASTQ file to the server's input directory.
    Returns the server-side path to use in pipeline parameters.
    """
    # Validate extension
    allowed_exts = {".fastq", ".fastq.gz", ".fq", ".fq.gz", ".fa", ".fasta", ".gtf", ".gff"}
    filename = file.filename or "upload"
    ext = "".join(Path(filename).suffixes).lower()
    if ext not in allowed_exts:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{ext}' not allowed. Accepted: {', '.join(sorted(allowed_exts))}",
        )

    # Save with unique name
    project_dir = UPLOAD_DIR / project
    project_dir.mkdir(parents=True, exist_ok=True)
    dest = project_dir / filename

    hasher = hashlib.sha256()
    size = 0
    with open(dest, "wb") as fh:
        while chunk := await file.read(8192):
            fh.write(chunk)
            hasher.update(chunk)
            size += len(chunk)

    return FileUploadResponse(
        filename=filename,
        path=str(dest),
        size_bytes=size,
        checksum=hasher.hexdigest(),
    )
