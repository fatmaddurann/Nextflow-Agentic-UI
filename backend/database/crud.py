"""
database/crud.py — Async CRUD operations for all ORM models.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .models import (
    AIAnalysis,
    ProcessMetric,
    SeverityLevel,
    WorkflowLog,
    WorkflowRun,
    WorkflowStatus,
)

# WorkflowRun CRUD


async def create_workflow(db: AsyncSession, workflow_data: dict[str, Any]) -> WorkflowRun:
    """Create a new WorkflowRun record."""
    workflow = WorkflowRun(**workflow_data)
    db.add(workflow)
    await db.flush()
    await db.refresh(workflow)
    return workflow


async def get_workflow(db: AsyncSession, workflow_id: str) -> WorkflowRun | None:
    """Fetch a workflow by its string ID."""
    result = await db.execute(
        select(WorkflowRun)
        .where(WorkflowRun.workflow_id == workflow_id)
        .options(selectinload(WorkflowRun.ai_analyses))
    )
    return result.scalar_one_or_none()


async def list_workflows(
    db: AsyncSession,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[WorkflowRun]:
    """List workflow runs with optional status filter and pagination."""
    q = select(WorkflowRun).order_by(desc(WorkflowRun.created_at))
    if status:
        q = q.where(WorkflowRun.status == status)
    q = q.limit(limit).offset(offset)
    result = await db.execute(q)
    return list(result.scalars().all())


async def update_workflow_status(
    db: AsyncSession,
    workflow_id: str,
    status: WorkflowStatus,
    **kwargs: Any,
) -> WorkflowRun | None:
    """Update workflow status and any additional fields."""
    values: dict[str, Any] = {"status": status, **kwargs}
    if status == WorkflowStatus.RUNNING and "started_at" not in kwargs:
        values["started_at"] = datetime.utcnow()
    if status in (WorkflowStatus.COMPLETED, WorkflowStatus.FAILED, WorkflowStatus.CANCELLED):
        if "completed_at" not in kwargs:
            values["completed_at"] = datetime.utcnow()

    await db.execute(
        update(WorkflowRun).where(WorkflowRun.workflow_id == workflow_id).values(**values)
    )
    await db.flush()
    return await get_workflow(db, workflow_id)


async def delete_workflow(db: AsyncSession, workflow_id: str) -> bool:
    """Soft-delete a workflow (cancel if running, then mark deleted)."""
    workflow = await get_workflow(db, workflow_id)
    if not workflow:
        return False
    await db.delete(workflow)
    await db.flush()
    return True


# WorkflowLog CRUD


async def add_log_entry(
    db: AsyncSession,
    workflow_id: str,
    message: str,
    level: SeverityLevel = SeverityLevel.INFO,
    process: str | None = None,
    raw_line: str | None = None,
) -> WorkflowLog:
    """Append a log entry for a workflow."""
    log = WorkflowLog(
        workflow_id=workflow_id,
        message=message,
        level=level,
        process=process,
        raw_line=raw_line,
        timestamp=datetime.utcnow(),
    )
    db.add(log)
    await db.flush()
    return log


async def get_workflow_logs(
    db: AsyncSession,
    workflow_id: str,
    level: str | None = None,
    limit: int = 500,
    offset: int = 0,
) -> list[WorkflowLog]:
    """Retrieve logs for a workflow, optionally filtered by severity."""
    q = (
        select(WorkflowLog)
        .where(WorkflowLog.workflow_id == workflow_id)
        .order_by(WorkflowLog.timestamp)
    )
    if level:
        q = q.where(WorkflowLog.level == level)
    q = q.limit(limit).offset(offset)
    result = await db.execute(q)
    return list(result.scalars().all())


async def count_logs_by_level(db: AsyncSession, workflow_id: str) -> dict[str, int]:
    """Count log entries per severity level for a workflow."""
    result = await db.execute(
        select(WorkflowLog.level, func.count(WorkflowLog.id))
        .where(WorkflowLog.workflow_id == workflow_id)
        .group_by(WorkflowLog.level)
    )
    return {row[0]: row[1] for row in result.all()}


# AIAnalysis CRUD


async def save_ai_analysis(db: AsyncSession, analysis_data: dict[str, Any]) -> AIAnalysis:
    """Persist an AI analysis result."""
    analysis = AIAnalysis(**analysis_data)
    db.add(analysis)
    await db.flush()
    await db.refresh(analysis)
    return analysis


async def get_latest_analysis(db: AsyncSession, workflow_id: str) -> AIAnalysis | None:
    """Get the most recent AI analysis for a workflow."""
    result = await db.execute(
        select(AIAnalysis)
        .where(AIAnalysis.workflow_id == workflow_id)
        .order_by(desc(AIAnalysis.created_at))
        .limit(1)
    )
    return result.scalar_one_or_none()


# ProcessMetric CRUD


async def bulk_save_process_metrics(
    db: AsyncSession,
    workflow_id: str,
    metrics: list[dict[str, Any]],
) -> int:
    """Bulk-insert process metrics from a Nextflow trace file."""
    objects = [ProcessMetric(workflow_id=workflow_id, **m) for m in metrics]
    db.add_all(objects)
    await db.flush()
    return len(objects)


async def get_process_metrics(db: AsyncSession, workflow_id: str) -> list[ProcessMetric]:
    result = await db.execute(
        select(ProcessMetric)
        .where(ProcessMetric.workflow_id == workflow_id)
        .order_by(ProcessMetric.started_at)
    )
    return list(result.scalars().all())


# Dashboard / Summary Queries


async def get_dashboard_summary(db: AsyncSession) -> dict[str, Any]:
    """Aggregate statistics for the dashboard."""
    status_counts_result = await db.execute(
        select(WorkflowRun.status, func.count(WorkflowRun.id)).group_by(WorkflowRun.status)
    )
    status_counts = {row[0]: row[1] for row in status_counts_result.all()}

    recent_result = await db.execute(
        select(WorkflowRun).order_by(desc(WorkflowRun.created_at)).limit(5)
    )
    recent_workflows = list(recent_result.scalars().all())

    return {
        "total_runs": sum(status_counts.values()),
        "status_counts": status_counts,
        "recent_workflows": [
            {
                "workflow_id": w.workflow_id,
                "name": w.name,
                "status": w.status,
                "created_at": w.created_at.isoformat() if w.created_at else None,
                "duration": w.duration_seconds,
            }
            for w in recent_workflows
        ],
    }
