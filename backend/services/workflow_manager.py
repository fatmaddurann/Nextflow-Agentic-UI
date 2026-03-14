"""
services/workflow_manager.py
Manages Nextflow pipeline launches, cancellations, and resumption.
"""

import asyncio
import os
import signal
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog

from database.crud import add_log_entry, create_workflow, get_workflow, update_workflow_status
from database.database import AsyncSessionLocal
from database.models import SeverityLevel, WorkflowStatus

log = structlog.get_logger(__name__)

# Configuration from environment
NF_BINARY = os.getenv("NEXTFLOW_BINARY", "nextflow")
NF_WORK_DIR = os.getenv("NEXTFLOW_WORK_DIR", "/pipeline/work")
NF_OUTPUT_DIR = os.getenv("NEXTFLOW_OUTPUT_DIR", "/pipeline/results")
NF_LOG_DIR = os.getenv("NEXTFLOW_LOG_DIR", "/pipeline/logs")
NF_SCRIPT = os.getenv("NEXTFLOW_SCRIPT", "/pipeline/src/main.nf")


class WorkflowManager:
    """
    Orchestrates Nextflow pipeline execution.
    Handles start / stop / resume and communicates status updates to the database.
    """

    # Registry of active subprocesses keyed by workflow_id
    _active_processes: dict[str, asyncio.subprocess.Process] = {}

    # Public API

    async def start_pipeline(
        self,
        name: str,
        pipeline_type: str = "rnaseq",
        profile: str = "docker",
        params: dict[str, Any] | None = None,
        owner: str = "anonymous",
        project_name: str | None = None,
        description: str | None = None,
    ) -> str:
        """
        Launch a Nextflow pipeline asynchronously.
        Returns the generated workflow_id.
        """
        workflow_id = self._generate_id()
        params = params or {}

        # Resolve paths
        work_dir = Path(NF_WORK_DIR) / workflow_id
        output_dir = Path(NF_OUTPUT_DIR) / workflow_id
        log_file = Path(NF_LOG_DIR) / f"{workflow_id}.log"

        for d in (work_dir, output_dir, Path(NF_LOG_DIR)):
            d.mkdir(parents=True, exist_ok=True)

        # Build Nextflow command
        cmd = self._build_command(
            workflow_id=workflow_id,
            profile=profile,
            work_dir=work_dir,
            output_dir=output_dir,
            log_file=log_file,
            params=params,
        )

        log.info("launching_pipeline", workflow_id=workflow_id, cmd=" ".join(cmd))

        # Persist workflow record
        async with AsyncSessionLocal() as db:
            await create_workflow(
                db,
                {
                    "workflow_id": workflow_id,
                    "name": name,
                    "pipeline_type": pipeline_type,
                    "status": WorkflowStatus.PENDING,
                    "profile": profile,
                    "owner": owner,
                    "project_name": project_name,
                    "description": description,
                    "work_dir": str(work_dir),
                    "output_dir": str(output_dir),
                    "log_file": str(log_file),
                    "input_params": params,
                },
            )
            await db.commit()

        # Launch async subprocess
        asyncio.create_task(self._run_pipeline(workflow_id, cmd, log_file))

        return workflow_id

    async def stop_pipeline(self, workflow_id: str) -> bool:
        """
        Terminate a running Nextflow process by workflow_id.
        Returns True if a process was found and killed.
        """
        proc = self._active_processes.get(workflow_id)
        if proc is None:
            log.warning("stop_pipeline_not_found", workflow_id=workflow_id)
            return False

        try:
            proc.send_signal(signal.SIGTERM)
            log.info("pipeline_sigterm_sent", workflow_id=workflow_id)
        except ProcessLookupError:
            pass  # Already exited

        async with AsyncSessionLocal() as db:
            await update_workflow_status(
                db, workflow_id, WorkflowStatus.CANCELLED, completed_at=datetime.utcnow()
            )
            await add_log_entry(
                db, workflow_id, "Pipeline manually cancelled by user.", SeverityLevel.WARNING
            )
            await db.commit()

        self._active_processes.pop(workflow_id, None)
        return True

    async def resume_pipeline(self, workflow_id: str) -> str | None:
        """
        Resume a previously-run (or failed) pipeline using Nextflow's -resume flag.
        Returns a new workflow_id (as Nextflow creates a fresh session ID internally).
        """
        async with AsyncSessionLocal() as db:
            original = await get_workflow(db, workflow_id)
            if not original:
                raise ValueError(f"Workflow {workflow_id!r} not found")

        new_workflow_id = self._generate_id()
        work_dir = (
            Path(original.work_dir) if original.work_dir else Path(NF_WORK_DIR) / new_workflow_id
        )
        output_dir = (
            Path(original.output_dir)
            if original.output_dir
            else Path(NF_OUTPUT_DIR) / new_workflow_id
        )
        log_file = Path(NF_LOG_DIR) / f"{new_workflow_id}.log"

        cmd = self._build_command(
            workflow_id=new_workflow_id,
            profile=original.profile,
            work_dir=work_dir,
            output_dir=output_dir,
            log_file=log_file,
            params=original.input_params or {},
            resume=True,
        )

        async with AsyncSessionLocal() as db:
            await create_workflow(
                db,
                {
                    "workflow_id": new_workflow_id,
                    "name": f"{original.name} (resumed)",
                    "pipeline_type": original.pipeline_type,
                    "status": WorkflowStatus.PENDING,
                    "profile": original.profile,
                    "owner": original.owner,
                    "project_name": original.project_name,
                    "description": f"Resumed from {workflow_id}",
                    "work_dir": str(work_dir),
                    "output_dir": str(output_dir),
                    "log_file": str(log_file),
                    "input_params": original.input_params,
                },
            )
            await db.commit()

        asyncio.create_task(self._run_pipeline(new_workflow_id, cmd, log_file))
        return new_workflow_id

    def list_active(self) -> list[str]:
        """Return workflow IDs of currently running processes."""
        return list(self._active_processes.keys())

    # Private helpers

    @staticmethod
    def _generate_id() -> str:
        return f"wf-{uuid.uuid4().hex[:12]}"

    @staticmethod
    def _build_command(
        workflow_id: str,
        profile: str,
        work_dir: Path,
        output_dir: Path,
        log_file: Path,
        params: dict[str, Any],
        resume: bool = False,
    ) -> list[str]:
        """Construct the full Nextflow CLI command."""
        cmd = [
            NF_BINARY,
            "run",
            NF_SCRIPT,
            "-profile",
            profile,
            "-work-dir",
            str(work_dir),
            "-log",
            str(log_file),
            "--outdir",
            str(output_dir),
            "-with-report",
            str(output_dir / "pipeline_info" / "execution_report.html"),
            "-with-trace",
            str(output_dir / "pipeline_info" / "execution_trace.txt"),
            "-with-timeline",
            str(output_dir / "pipeline_info" / "execution_timeline.html"),
            "-with-dag",
            str(output_dir / "pipeline_info" / "pipeline_dag.svg"),
            "-ansi-log",
            "false",  # Machine-parsable output
        ]

        if resume:
            cmd.append("-resume")

        # Add user-supplied params
        for key, val in params.items():
            if val is not None:
                cmd += [f"--{key}", str(val)]

        return cmd

    async def _run_pipeline(
        self,
        workflow_id: str,
        cmd: list[str],
        log_file: Path,
    ) -> None:
        """
        Execute the Nextflow command, stream stdout/stderr to the log file,
        and update the database on completion or failure.
        """
        log.info("pipeline_subprocess_start", workflow_id=workflow_id)

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env={**os.environ},
            )
            self._active_processes[workflow_id] = proc

            async with AsyncSessionLocal() as db:
                await update_workflow_status(
                    db,
                    workflow_id,
                    WorkflowStatus.RUNNING,
                    pid=proc.pid,
                    started_at=datetime.utcnow(),
                )
                await db.commit()

            # Stream output line-by-line to log file + DB
            with open(log_file, "w", encoding="utf-8") as fh:
                async for raw_line in proc.stdout:
                    line = raw_line.decode("utf-8", errors="replace").rstrip()
                    fh.write(line + "\n")
                    fh.flush()

                    level = self._classify_log_level(line)
                    async with AsyncSessionLocal() as db:
                        await add_log_entry(
                            db,
                            workflow_id,
                            message=self._clean_log_line(line),
                            level=level,
                            process=self._extract_process_name(line),
                            raw_line=line,
                        )
                        await db.commit()

            exit_code = await proc.wait()
            status = WorkflowStatus.COMPLETED if exit_code == 0 else WorkflowStatus.FAILED
            failed_process = None

            if exit_code != 0:
                failed_process = await self._detect_failed_process(log_file)
                log.error(
                    "pipeline_failed",
                    workflow_id=workflow_id,
                    exit_code=exit_code,
                    failed_process=failed_process,
                )

            async with AsyncSessionLocal() as db:
                await update_workflow_status(
                    db,
                    workflow_id,
                    status,
                    exit_code=exit_code,
                    failed_process=failed_process,
                    completed_at=datetime.utcnow(),
                )
                await db.commit()

            log.info(
                "pipeline_subprocess_done",
                workflow_id=workflow_id,
                status=status,
                exit_code=exit_code,
            )

        except Exception as exc:
            log.exception("pipeline_subprocess_error", workflow_id=workflow_id, error=str(exc))
            async with AsyncSessionLocal() as db:
                await update_workflow_status(
                    db,
                    workflow_id,
                    WorkflowStatus.FAILED,
                    error_message=str(exc),
                    completed_at=datetime.utcnow(),
                )
                await add_log_entry(
                    db, workflow_id, f"Internal launcher error: {exc}", SeverityLevel.CRITICAL
                )
                await db.commit()
        finally:
            self._active_processes.pop(workflow_id, None)

    @staticmethod
    def _classify_log_level(line: str) -> SeverityLevel:
        line_lower = line.lower()
        if any(k in line_lower for k in ("error", "exception", "failed", "exit code")):
            return SeverityLevel.ERROR
        if any(k in line_lower for k in ("warn", "warning")):
            return SeverityLevel.WARNING
        if "debug" in line_lower:
            return SeverityLevel.DEBUG
        return SeverityLevel.INFO

    @staticmethod
    def _clean_log_line(line: str) -> str:
        """Strip ANSI colour codes from a log line."""
        import re

        ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        return ansi_escape.sub("", line).strip()

    @staticmethod
    def _extract_process_name(line: str) -> str | None:
        """Try to extract a process name from Nextflow log output."""
        import re

        # e.g. "[ad/1f2e34] process > FASTQC (sample1) [100%]"
        m = re.search(r"process\s*>\s*(\S+)", line)
        return m.group(1) if m else None

    @staticmethod
    async def _detect_failed_process(log_file: Path) -> str | None:
        """Scan a log file to identify the first failing process."""
        import re

        try:
            content = log_file.read_text(encoding="utf-8", errors="replace")
            # Nextflow error pattern: "Error executing process > 'PROCESS_NAME'"
            m = re.search(r"Error executing process > ['\"]?(\w+)['\"]?", content, re.IGNORECASE)
            if m:
                return m.group(1)
            # Alternative: "FAILED [PROCESS]"
            m = re.search(r"\[.+\]\s+FAILED\s+(\S+)", content)
            if m:
                return m.group(1)
        except Exception:
            pass
        return None


# Singleton instance
workflow_manager = WorkflowManager()
