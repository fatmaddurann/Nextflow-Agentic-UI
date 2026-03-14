"""
services/log_monitor.py
Real-time log monitoring, failure detection, and WebSocket broadcasting.
"""

import asyncio
import os
import re
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog

from database.crud import get_workflow
from database.database import AsyncSessionLocal
from database.models import SeverityLevel, WorkflowStatus

log = structlog.get_logger(__name__)

POLL_INTERVAL = float(os.getenv("LOG_POLL_INTERVAL_SECONDS", "3"))
NF_LOG_DIR = os.getenv("NEXTFLOW_LOG_DIR", "/pipeline/logs")


# Failure Pattern Registry
FAILURE_PATTERNS: list[dict[str, Any]] = [
    # STAR errors
    {
        "pattern": re.compile(r"EXITING because of FATAL ERROR.*genomeDir", re.IGNORECASE),
        "category": "star_index_missing",
        "severity": SeverityLevel.CRITICAL,
        "hint": "STAR genome index is missing or corrupt. Regenerate with STAR_GENOMEGENERATE.",
    },
    {
        "pattern": re.compile(r"FATAL ERROR.*genomeSAindexNbases", re.IGNORECASE),
        "category": "star_genome_too_small",
        "severity": SeverityLevel.ERROR,
        "hint": "genomeSAindexNbases is too large for the genome size. Reduce it.",
    },
    # Memory / OOM errors
    {
        "pattern": re.compile(
            r"(out of memory|OOMKilled|Cannot allocate memory|Killed)", re.IGNORECASE
        ),
        "category": "out_of_memory",
        "severity": SeverityLevel.CRITICAL,
        "hint": "Process was killed due to insufficient memory. Increase process.memory in nextflow.config.",
    },
    {
        "pattern": re.compile(r"java\.lang\.OutOfMemoryError", re.IGNORECASE),
        "category": "jvm_oom",
        "severity": SeverityLevel.CRITICAL,
        "hint": "JVM out of memory. Increase NXF_JVM_ARGS or process memory limits.",
    },
    # File / path errors
    {
        "pattern": re.compile(r"No such file or directory", re.IGNORECASE),
        "category": "missing_file",
        "severity": SeverityLevel.ERROR,
        "hint": "A required input file or directory was not found. Check paths in your params.",
    },
    {
        "pattern": re.compile(r"(checkIfExists|does not exist|cannot find)", re.IGNORECASE),
        "category": "input_not_found",
        "severity": SeverityLevel.ERROR,
        "hint": "Input file check failed. Verify that --reads, --genome, or --gtf paths are correct.",
    },
    # Docker errors
    {
        "pattern": re.compile(
            r"(docker.*pull.*failed|Unable to find image|manifest unknown)", re.IGNORECASE
        ),
        "category": "docker_pull_failed",
        "severity": SeverityLevel.ERROR,
        "hint": "Docker container pull failed. Check internet connectivity and container registry access.",
    },
    {
        "pattern": re.compile(
            r"(docker.*permission denied|cannot connect to the Docker daemon)", re.IGNORECASE
        ),
        "category": "docker_permission",
        "severity": SeverityLevel.CRITICAL,
        "hint": "Docker permission denied. Ensure the user is in the docker group or the socket is accessible.",
    },
    # FastQC errors
    {
        "pattern": re.compile(r"uk\.ac\.babraham\.FastQC.*Exception", re.IGNORECASE),
        "category": "fastqc_error",
        "severity": SeverityLevel.ERROR,
        "hint": "FastQC encountered an error. Verify FASTQ file integrity and format.",
    },
    {
        "pattern": re.compile(
            r"(corrupt|truncated|invalid.*fastq|not a valid FASTQ)", re.IGNORECASE
        ),
        "category": "corrupt_fastq",
        "severity": SeverityLevel.ERROR,
        "hint": "FASTQ file appears corrupt or truncated. Re-download or re-demultiplex the sample.",
    },
    # Trimmomatic errors
    {
        "pattern": re.compile(
            r"(adapter.*not found|TruSeq.*not found|ILLUMINACLIP.*Error)", re.IGNORECASE
        ),
        "category": "trimmomatic_adapter",
        "severity": SeverityLevel.ERROR,
        "hint": "Trimmomatic adapter file not found. Set --trimmomatic_adapter to a valid adapter FASTA.",
    },
    # featureCounts / GTF errors
    {
        "pattern": re.compile(
            r"(GTF.*invalid|annotation.*error|featureCounts.*failed)", re.IGNORECASE
        ),
        "category": "featurecounts_gtf_error",
        "severity": SeverityLevel.ERROR,
        "hint": "featureCounts annotation error. Check that the GTF file matches the genome assembly.",
    },
    # Nextflow channel / DSL2 errors
    {
        "pattern": re.compile(
            r"(Channel.*mismatch|unexpected.*end.*of.*input|No signature of method)", re.IGNORECASE
        ),
        "category": "nextflow_dsl_error",
        "severity": SeverityLevel.ERROR,
        "hint": "Nextflow DSL2 channel error. Check module input/output type declarations.",
    },
    {
        "pattern": re.compile(r"(Missing required.*param|No.*argument.*provided)", re.IGNORECASE),
        "category": "missing_param",
        "severity": SeverityLevel.ERROR,
        "hint": "A required Nextflow parameter is missing. Add it to the run command or nextflow.config.",
    },
    # Process exit codes
    {
        "pattern": re.compile(r"exit status\s+(?:1[3-9][0-9]|[2-9][0-9])", re.IGNORECASE),
        "category": "high_exit_code",
        "severity": SeverityLevel.ERROR,
        "hint": "Process exited with a high error code, possibly from a signal kill (e.g., SIGKILL=137 = OOM).",
    },
    # Disk space
    {
        "pattern": re.compile(r"(no space left on device|disk full|quota exceeded)", re.IGNORECASE),
        "category": "disk_full",
        "severity": SeverityLevel.CRITICAL,
        "hint": "Disk space exhausted. Free up space in the work directory or mount a larger volume.",
    },
]


# WebSocket Connection Manager
class ConnectionManager:
    """Manages active WebSocket connections for real-time log streaming."""

    def __init__(self) -> None:
        self._connections: dict[str, set[Any]] = {}  # workflow_id -> set of WebSocket objects

    async def connect(self, workflow_id: str, websocket: Any) -> None:
        await websocket.accept()
        if workflow_id not in self._connections:
            self._connections[workflow_id] = set()
        self._connections[workflow_id].add(websocket)
        log.info(
            "ws_client_connected",
            workflow_id=workflow_id,
            total=len(self._connections[workflow_id]),
        )

    def disconnect(self, workflow_id: str, websocket: Any) -> None:
        if workflow_id in self._connections:
            self._connections[workflow_id].discard(websocket)
            if not self._connections[workflow_id]:
                del self._connections[workflow_id]

    async def broadcast(self, workflow_id: str, message: dict[str, Any]) -> None:
        """Send a message to all connected clients watching a workflow."""
        dead = set()
        for ws in list(self._connections.get(workflow_id, [])):
            try:
                await ws.send_json(message)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self.disconnect(workflow_id, ws)

    async def broadcast_all(self, message: dict[str, Any]) -> None:
        """Broadcast to every connected client (e.g. system alerts)."""
        for workflow_id in list(self._connections.keys()):
            await self.broadcast(workflow_id, message)


ws_manager = ConnectionManager()


# Log Monitor
class LogMonitor:
    """
    Polls Nextflow log files and detects failure patterns.
    On failure, triggers AI analysis (callback) and broadcasts to WebSockets.
    """

    def __init__(self) -> None:
        self._monitoring: dict[str, asyncio.Task] = {}
        self._on_failure_callbacks: list[Callable] = []

    def on_failure(self, callback: Callable) -> None:
        """Register a callback invoked when a pipeline failure is detected."""
        self._on_failure_callbacks.append(callback)

    async def start_monitoring(self, workflow_id: str, log_file: str) -> None:
        """Begin tailing a log file for a specific workflow."""
        if workflow_id in self._monitoring:
            log.warning("already_monitoring", workflow_id=workflow_id)
            return

        task = asyncio.create_task(
            self._tail_log(workflow_id, Path(log_file)), name=f"monitor-{workflow_id}"
        )
        self._monitoring[workflow_id] = task
        log.info("log_monitor_started", workflow_id=workflow_id, log_file=log_file)

    async def stop_monitoring(self, workflow_id: str) -> None:
        task = self._monitoring.pop(workflow_id, None)
        if task and not task.done():
            task.cancel()

    def list_monitored(self) -> list[str]:
        return list(self._monitoring.keys())

    # Internal tailing loop

    async def _tail_log(self, workflow_id: str, log_file: Path) -> None:
        """
        Follow a log file as it grows (like `tail -f`).
        Detect failure patterns and dispatch callbacks.
        """
        detected_failures: set[str] = set()
        position = 0

        while True:
            try:
                # Check if workflow is still running
                async with AsyncSessionLocal() as db:
                    wf = await get_workflow(db, workflow_id)
                    if wf and wf.status not in (WorkflowStatus.RUNNING, WorkflowStatus.PENDING):
                        log.info(
                            "monitor_workflow_terminal", workflow_id=workflow_id, status=wf.status
                        )
                        break

                if not log_file.exists():
                    await asyncio.sleep(POLL_INTERVAL)
                    continue

                with open(log_file, encoding="utf-8", errors="replace") as fh:
                    fh.seek(position)
                    new_lines = fh.readlines()
                    position = fh.tell()

                for raw_line in new_lines:
                    line = raw_line.rstrip()
                    if not line:
                        continue

                    # Broadcast to WebSocket clients
                    await ws_manager.broadcast(
                        workflow_id,
                        {
                            "type": "log_line",
                            "workflow_id": workflow_id,
                            "timestamp": datetime.utcnow().isoformat(),
                            "line": self._strip_ansi(line),
                            "level": self._classify(line),
                        },
                    )

                    # Check for known failure patterns
                    for fp in FAILURE_PATTERNS:
                        if fp["pattern"].search(line) and fp["category"] not in detected_failures:
                            detected_failures.add(fp["category"])
                            log.warning(
                                "failure_pattern_detected",
                                workflow_id=workflow_id,
                                category=fp["category"],
                                hint=fp["hint"],
                            )
                            await ws_manager.broadcast(
                                workflow_id,
                                {
                                    "type": "failure_detected",
                                    "workflow_id": workflow_id,
                                    "category": fp["category"],
                                    "hint": fp["hint"],
                                    "severity": fp["severity"],
                                    "line": self._strip_ansi(line),
                                },
                            )

                            # Fire failure callbacks (e.g., trigger AI analysis)
                            for cb in self._on_failure_callbacks:
                                asyncio.create_task(cb(workflow_id, fp["category"], line))

            except asyncio.CancelledError:
                break
            except Exception as exc:
                log.error("log_monitor_error", workflow_id=workflow_id, error=str(exc))

            await asyncio.sleep(POLL_INTERVAL)

        self._monitoring.pop(workflow_id, None)

    # Helpers

    @staticmethod
    def _strip_ansi(line: str) -> str:
        return re.sub(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])", "", line)

    @staticmethod
    def _classify(line: str) -> str:
        lower = line.lower()
        if any(k in lower for k in ("error", "fatal", "failed", "exception")):
            return "error"
        if any(k in lower for k in ("warn", "warning")):
            return "warning"
        return "info"

    # Trace File Parser

    @staticmethod
    async def parse_trace_file(trace_path: str) -> list[dict[str, Any]]:
        """
        Parse a Nextflow trace.txt file into a list of process metric dicts.
        """
        records = []
        path = Path(trace_path)
        if not path.exists():
            return records

        with open(path, encoding="utf-8") as fh:
            lines = fh.readlines()

        if len(lines) < 2:
            return records

        headers = lines[0].rstrip().split("\t")

        def safe_float(v: str) -> float | None:
            try:
                # Handle Nextflow's memory notation (e.g. "1.2 GB")
                v = v.strip()
                if " " in v:
                    val, unit = v.split(maxsplit=1)
                    multipliers = {"KB": 1 / 1024, "MB": 1.0, "GB": 1024.0, "TB": 1024**2}
                    return float(val) * multipliers.get(unit.upper(), 1.0)
                return float(v) if v not in ("", "-") else None
            except (ValueError, TypeError):
                return None

        for line in lines[1:]:
            if not line.strip():
                continue
            values = line.rstrip("\n").split("\t")
            row = dict(zip(headers, values, strict=False))
            records.append(
                {
                    "task_id": row.get("task_id"),
                    "process_name": row.get("process", ""),
                    "tag": row.get("tag") or None,
                    "status": row.get("status"),
                    "exit_code": int(row["exit"])
                    if row.get("exit", "-") not in ("", "-")
                    else None,
                    "duration": safe_float(row.get("duration", "")),
                    "realtime": safe_float(row.get("realtime", "")),
                    "cpus": safe_float(row.get("cpus", "")),
                    "peak_rss_mb": safe_float(row.get("peak_rss", "")),
                    "peak_vmem_mb": safe_float(row.get("peak_vmem", "")),
                    "read_mb": safe_float(row.get("rchar", "")),
                    "write_mb": safe_float(row.get("wchar", "")),
                    "container": row.get("container") or None,
                }
            )

        return records


# Singleton instance
log_monitor = LogMonitor()
