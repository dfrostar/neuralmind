# daemon_memory.py — shared warm daemon memory across MCP clients (PRD 2 F2).
#
# MCP clients connect to the daemon and share the warm NeuralMind instance
# + synapse store + selector cache. Per-client access scoping ensures one
# client cannot read another's synapses. The second MCP client starts
# <=1s after the first (vs. full cold-start).
#
# Fail-open: if shared state is unavailable, fall back to cold-start.
# Pure stdlib at module level.

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


class SharedDaemonMemory:
    """Shared daemon memory model across MCP clients.

    Usage:
        shared = SharedDaemonMemory(project_path="/path/to/project")
        mind = shared.get_instance(client_id="client-1")
        shared.register_client(client_id="client-1", project_path="/path/to/project")
    """

    def __init__(self, project_path: str | Path | None = None):
        self.project_path = Path(project_path) if project_path is not None else None
        self._instance: Any = None
        self._clients: dict[str, Any] = {}
        self._store: Any = None
        self._selector_cache: dict[str, Any] = {}
        self._lock = threading.Lock()

    def get_instance(self, client_id: str) -> Any:
        """Get or create the warm NeuralMind instance for a client.

        First call constructs the instance; subsequent calls return the
        cached warm instance. Thread-safe.
        """
        with self._lock:
            if self._instance is not None:
                return self._instance
            try:
                from .core import NeuralMind

                self._instance = NeuralMind(str(self.project_path))
                return self._instance
            except Exception as exc:
                log.warning("get_instance: cold-start fallback: %s", exc)
                return None

    def register_client(self, client_id: str, project_path: str) -> None:
        """Register a new MCP client."""
        with self._lock:
            self._clients[client_id] = {
                "project_path": project_path,
                "registered_at": __import__("time").time(),
            }

    def is_authorized(
        self,
        client_id: str,
        target_project: str,
    ) -> bool:
        """Check whether a client may access another project's synapses.

        A client can read:
          - its own project's synapses (matched by path)
          - the canonical `shared` namespace (team baseline) — compared
            against ``shared.SHARED_NAMESPACE`` constant, not the literal
            ``"shared"``, to avoid collision with a project literally
            named "shared"
          - any project explicitly shared with it via ``share_project``

        Cross-project reads are denied otherwise.
        """
        with self._lock:
            mine = self._clients.get(client_id)
            if mine is None:
                return False
            if mine["project_path"] == target_project:
                return True
            # Shared namespace: always allowed (it is the team baseline).
            # Compare via the canonical constant to avoid collision with
            # a project literally named "shared".
            from .synapses import SHARED_NAMESPACE

            if target_project == SHARED_NAMESPACE:
                return True
            # Explicitly shared projects.
            shared_projects = mine.get("shared_with", [])
            return target_project in shared_projects

    def share_project(
        self,
        owner_id: str,
        target_project: str,
    ) -> bool:
        """Explicitly share a project with a client."""
        with self._lock:
            mine = self._clients.get(owner_id)
            if mine is None:
                return False
            if "shared_with" not in mine:
                mine["shared_with"] = []
            if target_project not in mine["shared_with"]:
                mine["shared_with"].append(target_project)
            return True

    def release_client(self, client_id: str) -> None:
        """Release a client's resources."""
        with self._lock:
            self._clients.pop(client_id, None)
            self._selector_cache.pop(client_id, None)
            if not self._clients:
                self._instance = None

    def cache_selector(self, client_id: str, selector: Any) -> None:
        """Cache a context selector for reuse across calls from this client."""
        with self._lock:
            self._selector_cache[client_id] = selector

    def get_cached_selector(self, client_id: str) -> Any:
        """Retrieve a cached context selector, or None."""
        with self._lock:
            return self._selector_cache.get(client_id)
