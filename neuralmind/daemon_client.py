"""Thin client for the NeuralMind daemon (PRD 5).

Stdlib-only (``urllib``) so importing it never pulls a transport dependency.
The client discovers the daemon via its per-user discovery file, pings
``/health``, and cleans up a stale file (dead pid / unreachable) so a crashed
daemon never wedges the CLI — the caller just falls back to direct mode.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

from .daemon import _pid_alive, clear_discovery, read_discovery


class DaemonUnavailableError(Exception):
    """Raised when no reachable daemon is found."""


class DaemonClient:
    def __init__(self, info: dict) -> None:
        self.host = info.get("host", "127.0.0.1")
        self.port = int(info["port"])
        self.token = info.get("token")
        self.base = f"http://{self.host}:{self.port}"

    # -- transport ------------------------------------------------------- #
    def _request(
        self, method: str, route: str, body: dict | None = None, timeout: float = 30.0
    ) -> dict:
        url = f"{self.base}{route}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        if self.token:
            req.add_header("Authorization", f"Bearer {self.token}")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            # Auth failures mean the daemon is unusable for us → fall back to
            # direct mode. App-level errors (400/404/500) come back as JSON so
            # the caller can inspect {"error": ...}.
            if exc.code in (401, 403):
                raise DaemonUnavailableError(f"auth rejected (HTTP {exc.code})") from exc
            try:
                return json.loads(exc.read().decode("utf-8"))
            except Exception:
                raise DaemonUnavailableError(f"daemon HTTP {exc.code}") from exc
        except (urllib.error.URLError, OSError, ValueError) as exc:
            raise DaemonUnavailableError(str(exc)) from exc

    # -- API ------------------------------------------------------------- #
    def health(self, timeout: float = 2.0) -> dict:
        # Short timeout: this is the liveness probe behind the CLI's
        # daemon-or-direct decision, so an unresponsive daemon must fall back
        # fast rather than stalling every command.
        return self._request("GET", "/health", timeout=timeout)

    def status(self) -> dict:
        return self._request("GET", "/status")

    def query(
        self, project: str, question: str, trace: bool = False, trace_verbose: bool = False
    ) -> dict:
        return self._request(
            "POST",
            "/query",
            {
                "project": project,
                "question": question,
                "trace": trace,
                "trace_verbose": trace_verbose,
            },
            timeout=120.0,
        )

    def search(self, project: str, query: str, n: int = 10) -> dict:
        return self._request("POST", "/search", {"project": project, "query": query, "n": n})

    def stats(self, project: str) -> dict:
        return self._request("GET", f"/stats?project={urllib.parse.quote(project)}")

    def build(self, project: str, force: bool = False, sync: bool = False) -> dict:
        return self._request(
            "POST",
            "/build",
            {"project": project, "force": force, "sync": sync},
            timeout=600.0 if sync else 30.0,
        )

    def validate(self, project: str, write: bool = False) -> dict:
        return self._request("POST", "/validate", {"project": project, "write": write})

    def shutdown(self) -> dict:
        return self._request("POST", "/shutdown", {}, timeout=5.0)


def connect(*, ping: bool = True) -> DaemonClient | None:
    """Return a client for a running daemon, or ``None`` if none is reachable.

    Reads the discovery file. If the recorded pid is **dead**, the file is stale
    and gets cleared. If the pid is alive but ``/health`` is unreachable, the
    daemon is still starting (the socket binds before ``serve_forever`` accepts)
    or transiently busy — we return ``None`` **without** clearing, so a startup
    race can't orphan a daemon that's about to be ready. Callers fall back to
    direct mode for that invocation and a later call connects.
    """
    info = read_discovery()
    if not info:
        return None
    pid = info.get("pid")
    if isinstance(pid, int) and not _pid_alive(pid):
        clear_discovery()
        return None
    client = DaemonClient(info)
    if ping:
        try:
            client.health()
        except DaemonUnavailableError:
            return None
    return client


def is_running() -> bool:
    return connect(ping=True) is not None
