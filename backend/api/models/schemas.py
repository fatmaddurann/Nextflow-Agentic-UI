"""
api/models/schemas.py — Pydantic v2 request/response schemas.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

# Workflow Schemas


class WorkflowCreateRequest(BaseModel):
    """Request body to start a new pipeline run."""

    name: str = Field(..., min_length=1, max_length=255, description="Friendly name for this run")
    pipeline_type: str = Field("rnaseq", description="Pipeline type: rnaseq | wes | custom")
    profile: str = Field("docker", description="Nextflow profile to use")
    project_name: str | None = Field(None, description="Project / experiment name")
    owner: str | None = Field("anonymous", description="Submitting user")
    description: str | None = Field(None, description="Free-text description")

    # Nextflow params (forwarded as --param=value)
    reads: str | None = Field(None, description="Glob pattern or path to FASTQ files")
    genome: str | None = Field(None, description="Path to reference genome FASTA")
    gtf: str | None = Field(None, description="Path to GTF annotation file")
    star_index: str | None = Field(None, description="Path to pre-built STAR index")
    extra_params: dict[str, Any] = Field(
        default_factory=dict, description="Additional Nextflow params"
    )

    @field_validator("pipeline_type")
    @classmethod
    def validate_pipeline_type(cls, v: str) -> str:
        allowed = {"rnaseq", "wes", "custom"}
        if v.lower() not in allowed:
            raise ValueError(f"pipeline_type must be one of {allowed}")
        return v.lower()


class WorkflowResponse(BaseModel):
    """Full workflow run response."""

    workflow_id: str
    name: str
    pipeline_type: str
    status: str
    profile: str
    project_name: str | None
    owner: str
    description: str | None
    pid: int | None
    work_dir: str | None
    output_dir: str | None
    log_file: str | None
    created_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    duration_seconds: float | None
    failed_process: str | None
    exit_code: int | None
    error_message: str | None
    container_ids: list[str] = []
    input_params: dict[str, Any] = {}

    model_config = {"from_attributes": True}


class WorkflowListResponse(BaseModel):
    """Paginated list of workflow runs."""

    total: int
    page: int
    page_size: int
    items: list[WorkflowResponse]


# Log Schemas


class LogResponse(BaseModel):
    """A single log entry."""

    id: int
    workflow_id: str
    timestamp: datetime | None
    level: str
    process: str | None
    message: str
    raw_line: str | None

    model_config = {"from_attributes": True}


class LogListResponse(BaseModel):
    """Paginated log entries."""

    workflow_id: str
    total: int
    items: list[LogResponse]


# AI Analysis Schemas


class RAGSource(BaseModel):
    """A retrieved document from the knowledge base."""

    doc_id: str
    title: str
    category: str | None
    relevance: float  # 0-1 cosine similarity


class AIAnalysisResponse(BaseModel):
    """AI agent analysis result for a failed pipeline."""

    id: int
    workflow_id: str
    created_at: datetime | None
    error_summary: str
    root_cause: str | None
    affected_steps: list[str]
    suggestions: list[str]
    rag_sources: list[dict[str, Any]] = []
    confidence: float
    model_used: str | None
    tokens_used: int
    full_response: str | None

    model_config = {"from_attributes": True}


class TriggerAnalysisRequest(BaseModel):
    """Manually trigger AI analysis on a workflow."""

    workflow_id: str
    force: bool = Field(False, description="Re-analyse even if analysis already exists")


# Container Schemas


class ContainerInfo(BaseModel):
    """Docker container metadata."""

    container_id: str
    name: str
    image: str
    status: str
    state: str  # running | exited | paused
    created: str | None
    workflow_id: str | None
    exit_code: int | None
    cpu_percent: float | None
    memory_mb: float | None


# Process Metric Schemas


class ProcessMetricResponse(BaseModel):
    process_name: str
    tag: str | None
    status: str | None
    exit_code: int | None
    duration: float | None
    cpus: float | None
    peak_rss_mb: float | None
    peak_vmem_mb: float | None
    container: str | None

    model_config = {"from_attributes": True}


# Dashboard / Health Schemas


class DashboardSummary(BaseModel):
    """High-level stats for the UI dashboard."""

    total_runs: int
    status_counts: dict[str, int]
    recent_workflows: list[dict[str, Any]]
    active_containers: int = 0


class HealthResponse(BaseModel):
    """API health-check response."""

    status: str
    version: str
    database: str
    docker: str
    nextflow: str
    chromadb: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# File Upload Schema


class FileUploadResponse(BaseModel):
    filename: str
    path: str
    size_bytes: int
    checksum: str
