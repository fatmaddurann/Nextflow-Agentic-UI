"""
monitoring/monitor.py — Standalone monitoring sidecar.

Polls the Nextflow log directory for new log files and forwards
trace data back to the FastAPI backend via HTTP.
"""

import asyncio
import os
from pathlib import Path
import httpx
import structlog

log = structlog.get_logger(__name__)

BACKEND_URL  = os.getenv("BACKEND_URL", "http://backend:8000")
LOG_DIR      = Path(os.getenv("NEXTFLOW_LOG_DIR", "/pipeline/logs"))
WORK_DIR     = Path(os.getenv("NEXTFLOW_WORK_DIR", "/pipeline/work"))
POLL_SECONDS = float(os.getenv("MONITOR_POLL_SECONDS", "10"))


async def poll_and_report():
    """Periodically scan for new trace files and report them to the backend."""
    async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=30) as client:
        seen_traces: set = set()

        while True:
            try:
                # Find all trace files (execution_trace.txt) in output dirs
                for trace_file in Path("/pipeline/results").glob("**/execution_trace.txt"):
                    if str(trace_file) not in seen_traces:
                        seen_traces.add(str(trace_file))
                        # Extract workflow_id from path
                        workflow_id = trace_file.parts[-3]  # results/{workflow_id}/pipeline_info/
                        log.info("trace_file_found", path=str(trace_file), workflow_id=workflow_id)

                        # Notify backend to parse the trace
                        try:
                            resp = await client.post(
                                f"/api/v1/workflows/{workflow_id}/parse-trace",
                                json={"trace_path": str(trace_file)},
                            )
                            if resp.status_code == 200:
                                log.info("trace_reported", workflow_id=workflow_id)
                        except Exception as e:
                            log.warning("trace_report_failed", error=str(e))

                # Health ping
                try:
                    await client.get("/health")
                except Exception:
                    log.warning("backend_unreachable")

            except Exception as exc:
                log.error("monitor_poll_error", error=str(exc))

            await asyncio.sleep(POLL_SECONDS)


if __name__ == "__main__":
    log.info("monitoring_sidecar_started", log_dir=str(LOG_DIR))
    asyncio.run(poll_and_report())
