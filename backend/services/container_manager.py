"""
services/container_manager.py
Docker SDK integration for container lifecycle management.
"""

import asyncio
import os
from typing import Any

import structlog

try:
    import docker
    from docker.errors import DockerException, NotFound

    DOCKER_AVAILABLE = True
except ImportError:
    DOCKER_AVAILABLE = False

log = structlog.get_logger(__name__)

DOCKER_SOCKET = os.getenv("DOCKER_SOCKET", "/var/run/docker.sock")
NF_LABEL = "nextflow-agentic"


class ContainerManager:
    """
    Wraps Docker SDK for Python to manage containers spawned by Nextflow.
    Uses the Docker socket for real-time container lifecycle monitoring.
    """

    def __init__(self) -> None:
        self._client: Any | None = None

    # Initialization

    def _get_client(self) -> Any:
        if not DOCKER_AVAILABLE:
            raise RuntimeError("docker Python package is not installed")
        if self._client is None:
            try:
                self._client = docker.DockerClient(base_url=f"unix://{DOCKER_SOCKET}")
                self._client.ping()
            except DockerException as e:
                log.warning("docker_connect_failed", error=str(e))
                self._client = None
                raise
        return self._client

    # Container Listing

    async def list_containers(
        self,
        workflow_id: str | None = None,
        all_containers: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Return all Docker containers, optionally filtered by workflow label.
        Runs synchronous Docker call in a thread pool to avoid blocking the event loop.
        """
        return await asyncio.to_thread(self._list_containers_sync, workflow_id, all_containers)

    def _list_containers_sync(
        self, workflow_id: str | None, all_containers: bool
    ) -> list[dict[str, Any]]:
        try:
            client = self._get_client()
            filters: dict[str, Any] = {}
            if workflow_id:
                filters["label"] = f"nextflow.workflowId={workflow_id}"

            containers = client.containers.list(all=all_containers, filters=filters)
            return [self._container_to_dict(c) for c in containers]
        except Exception as exc:
            log.error("list_containers_error", error=str(exc))
            return []

    # Container State

    async def get_container(self, container_id: str) -> dict[str, Any] | None:
        """Fetch details for a specific container."""
        return await asyncio.to_thread(self._get_container_sync, container_id)

    def _get_container_sync(self, container_id: str) -> dict[str, Any] | None:
        try:
            client = self._get_client()
            container = client.containers.get(container_id)
            return self._container_to_dict(container)
        except NotFound:
            return None
        except Exception as exc:
            log.error("get_container_error", container_id=container_id, error=str(exc))
            return None

    # Container Lifecycle

    async def restart_container(self, container_id: str) -> bool:
        """Restart a specific container."""
        return await asyncio.to_thread(self._restart_container_sync, container_id)

    def _restart_container_sync(self, container_id: str) -> bool:
        try:
            client = self._get_client()
            container = client.containers.get(container_id)
            container.restart(timeout=30)
            log.info("container_restarted", container_id=container_id)
            return True
        except Exception as exc:
            log.error("restart_container_error", container_id=container_id, error=str(exc))
            return False

    async def stop_container(self, container_id: str, timeout: int = 30) -> bool:
        """Stop a running container gracefully."""
        return await asyncio.to_thread(self._stop_container_sync, container_id, timeout)

    def _stop_container_sync(self, container_id: str, timeout: int) -> bool:
        try:
            client = self._get_client()
            container = client.containers.get(container_id)
            container.stop(timeout=timeout)
            log.info("container_stopped", container_id=container_id)
            return True
        except NotFound:
            return False
        except Exception as exc:
            log.error("stop_container_error", container_id=container_id, error=str(exc))
            return False

    async def remove_container(self, container_id: str, force: bool = False) -> bool:
        """Remove a stopped container."""
        return await asyncio.to_thread(self._remove_container_sync, container_id, force)

    def _remove_container_sync(self, container_id: str, force: bool) -> bool:
        try:
            client = self._get_client()
            container = client.containers.get(container_id)
            container.remove(force=force)
            log.info("container_removed", container_id=container_id)
            return True
        except NotFound:
            return False
        except Exception as exc:
            log.error("remove_container_error", container_id=container_id, error=str(exc))
            return False

    # Container Logs

    async def get_container_logs(
        self,
        container_id: str,
        tail: int = 200,
    ) -> str:
        """Fetch recent logs from a container."""
        return await asyncio.to_thread(self._get_container_logs_sync, container_id, tail)

    def _get_container_logs_sync(self, container_id: str, tail: int) -> str:
        try:
            client = self._get_client()
            container = client.containers.get(container_id)
            raw = container.logs(tail=tail, timestamps=True)
            return raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)
        except Exception as exc:
            log.error("container_logs_error", container_id=container_id, error=str(exc))
            return f"[Error fetching logs: {exc}]"

    # Resource Stats

    async def get_container_stats(self, container_id: str) -> dict[str, Any] | None:
        """Get one-shot CPU / memory statistics for a running container."""
        return await asyncio.to_thread(self._get_container_stats_sync, container_id)

    def _get_container_stats_sync(self, container_id: str) -> dict[str, Any] | None:
        try:
            client = self._get_client()
            container = client.containers.get(container_id)
            if container.status != "running":
                return None
            stats = container.stats(stream=False)
            return self._parse_stats(stats)
        except Exception as exc:
            log.error("container_stats_error", container_id=container_id, error=str(exc))
            return None

    @staticmethod
    def _parse_stats(stats: dict[str, Any]) -> dict[str, Any]:
        """Extract CPU % and memory MB from raw Docker stats."""
        try:
            cpu_delta = (
                stats["cpu_stats"]["cpu_usage"]["total_usage"]
                - stats["precpu_stats"]["cpu_usage"]["total_usage"]
            )
            sys_delta = (
                stats["cpu_stats"]["system_cpu_usage"] - stats["precpu_stats"]["system_cpu_usage"]
            )
            num_cpus = stats["cpu_stats"].get("online_cpus") or len(
                stats["cpu_stats"]["cpu_usage"].get("percpu_usage", [1])
            )
            cpu_pct = (cpu_delta / sys_delta) * num_cpus * 100.0 if sys_delta > 0 else 0.0

            mem_usage = stats["memory_stats"].get("usage", 0)
            mem_limit = stats["memory_stats"].get("limit", 1)
            mem_mb = mem_usage / (1024**2)
            mem_pct = (mem_usage / mem_limit) * 100.0

            return {
                "cpu_percent": round(cpu_pct, 2),
                "memory_mb": round(mem_mb, 2),
                "memory_percent": round(mem_pct, 2),
                "memory_limit_mb": round(mem_limit / (1024**2), 2),
            }
        except (KeyError, ZeroDivisionError):
            return {"cpu_percent": 0.0, "memory_mb": 0.0}

    # Cleanup

    async def cleanup_exited_containers(self) -> int:
        """Remove all exited containers (pruning)."""
        return await asyncio.to_thread(self._cleanup_exited_sync)

    def _cleanup_exited_sync(self) -> int:
        try:
            client = self._get_client()
            result = client.containers.prune(filters={"status": "exited"})
            count = len(result.get("ContainersDeleted") or [])
            log.info("containers_pruned", count=count)
            return count
        except Exception as exc:
            log.error("cleanup_containers_error", error=str(exc))
            return 0

    # Health Check

    async def health_check(self) -> str:
        """Return 'ok' if Docker is reachable, 'unavailable' otherwise."""
        try:
            client = self._get_client()
            client.ping()
            return "ok"
        except Exception:
            return "unavailable"

    # Private helpers

    @staticmethod
    def _container_to_dict(container: Any) -> dict[str, Any]:
        """Convert a Docker Container object to a serialisable dict."""
        attrs = container.attrs or {}
        state = attrs.get("State", {})
        config = attrs.get("Config", {})
        labels = config.get("Labels", {}) or {}

        return {
            "container_id": container.short_id,
            "full_id": container.id,
            "name": container.name,
            "image": (container.image.tags or [str(container.image.id)])[0]
            if container.image
            else "unknown",
            "status": container.status,
            "state": state.get("Status", "unknown"),
            "created": attrs.get("Created"),
            "exit_code": state.get("ExitCode"),
            "error": state.get("Error") or None,
            "workflow_id": labels.get("nextflow.workflowId"),
            "process_name": labels.get("nextflow.process"),
        }


# Singleton instance
container_manager = ContainerManager()
