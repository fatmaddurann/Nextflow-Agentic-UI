"""
database/models.py — SQLAlchemy ORM Models for Nextflow-Agentic-UI
"""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


# Enum Types
class WorkflowStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class PipelineType(StrEnum):
    RNASEQ = "rnaseq"
    WES = "wes"
    CUSTOM = "custom"


class SeverityLevel(StrEnum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


# ORM Models
class WorkflowRun(Base):
    """Tracks a single Nextflow pipeline execution."""

    __tablename__ = "workflow_runs"

    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(String(64), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    pipeline_type = Column(Enum(PipelineType), default=PipelineType.RNASEQ)
    status = Column(Enum(WorkflowStatus), default=WorkflowStatus.PENDING, index=True)

    # User / project metadata
    project_name = Column(String(255), nullable=True)
    owner = Column(String(128), default="anonymous")
    description = Column(Text, nullable=True)

    # Input configuration
    input_params = Column(JSON, default=dict)  # Nextflow params as JSON
    input_files = Column(JSON, default=list)  # Uploaded file paths
    profile = Column(String(64), default="docker")

    # Execution metadata
    pid = Column(Integer, nullable=True)  # OS PID of nextflow process
    work_dir = Column(String(512), nullable=True)
    output_dir = Column(String(512), nullable=True)
    log_file = Column(String(512), nullable=True)
    nextflow_session_id = Column(String(64), nullable=True)

    # Timing
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, nullable=True)

    # Failure info
    failed_process = Column(String(255), nullable=True)
    exit_code = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)

    # Container tracking
    container_ids = Column(JSON, default=list)

    # Relationships
    logs = relationship("WorkflowLog", back_populates="workflow", cascade="all, delete-orphan")
    ai_analyses = relationship(
        "AIAnalysis", back_populates="workflow", cascade="all, delete-orphan"
    )
    process_metrics = relationship(
        "ProcessMetric", back_populates="workflow", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<WorkflowRun id={self.workflow_id} status={self.status}>"


class WorkflowLog(Base):
    """Individual log entries captured from pipeline execution."""

    __tablename__ = "workflow_logs"

    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(
        String(64), ForeignKey("workflow_runs.workflow_id", ondelete="CASCADE"), index=True
    )
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    level = Column(Enum(SeverityLevel), default=SeverityLevel.INFO)
    process = Column(String(255), nullable=True)  # Which Nextflow process generated this log
    message = Column(Text, nullable=False)
    raw_line = Column(Text, nullable=True)  # Original unprocessed log line

    workflow = relationship("WorkflowRun", back_populates="logs")

    def __repr__(self) -> str:
        return f"<WorkflowLog {self.timestamp} [{self.level}] {self.message[:60]}>"


class AIAnalysis(Base):
    """AI agent analysis results for failed/warning workflows."""

    __tablename__ = "ai_analyses"

    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(
        String(64), ForeignKey("workflow_runs.workflow_id", ondelete="CASCADE"), index=True
    )
    created_at = Column(DateTime, default=datetime.utcnow)

    # Analysis content
    error_summary = Column(Text, nullable=False)
    root_cause = Column(Text, nullable=True)
    affected_steps = Column(JSON, default=list)  # List of failed process names
    suggestions = Column(JSON, default=list)  # List of suggestion strings
    rag_sources = Column(JSON, default=list)  # Retrieved knowledge base references
    confidence = Column(Float, default=0.0)  # AI confidence score 0-1
    model_used = Column(String(64), nullable=True)
    tokens_used = Column(Integer, default=0)
    full_response = Column(Text, nullable=True)  # Raw LLM response

    workflow = relationship("WorkflowRun", back_populates="ai_analyses")

    def __repr__(self) -> str:
        return f"<AIAnalysis workflow={self.workflow_id} confidence={self.confidence:.2f}>"


class ProcessMetric(Base):
    """Per-process resource usage metrics from Nextflow trace."""

    __tablename__ = "process_metrics"

    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(
        String(64), ForeignKey("workflow_runs.workflow_id", ondelete="CASCADE"), index=True
    )
    task_id = Column(String(64), nullable=True)
    process_name = Column(String(255), nullable=False)
    tag = Column(String(255), nullable=True)
    status = Column(String(32), nullable=True)
    exit_code = Column(Integer, nullable=True)

    # Timing (seconds)
    duration = Column(Float, nullable=True)
    realtime = Column(Float, nullable=True)

    # Resources
    cpus = Column(Float, nullable=True)
    peak_rss_mb = Column(Float, nullable=True)  # Memory (MB)
    peak_vmem_mb = Column(Float, nullable=True)
    read_mb = Column(Float, nullable=True)  # Disk read (MB)
    write_mb = Column(Float, nullable=True)  # Disk write (MB)

    container = Column(String(512), nullable=True)
    submitted_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    workflow = relationship("WorkflowRun", back_populates="process_metrics")

    def __repr__(self) -> str:
        return f"<ProcessMetric {self.process_name} status={self.status}>"


class KnowledgeDocument(Base):
    """Metadata for documents indexed in the RAG knowledge base."""

    __tablename__ = "knowledge_documents"

    id = Column(Integer, primary_key=True, index=True)
    doc_id = Column(String(128), unique=True, nullable=False)
    title = Column(String(512), nullable=False)
    category = Column(String(128), nullable=True)  # e.g. "star_errors", "memory_issues"
    content = Column(Text, nullable=False)
    source = Column(String(512), nullable=True)  # Origin reference
    tags = Column(JSON, default=list)
    embedding_id = Column(String(256), nullable=True)  # ChromaDB document ID
    indexed_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    def __repr__(self) -> str:
        return f"<KnowledgeDocument {self.doc_id}: {self.title[:60]}>"
