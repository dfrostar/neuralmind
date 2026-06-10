"""NeuralMind local daemon (PRD 5, Phase 1 — experimental).

The durable long-term boundary for NeuralMind is a *local service* that owns
project state, the index lifecycle, caching, and concurrency — with thin CLI,
MCP, and UI clients on top. Today every `neuralmind` invocation re-initializes
the backend, reloads the graph, and re-opens the index from cold; a daemon
initializes each project **once** and reuses it across requests, so warm
queries skip all of that.

Architecture
------------
- **One per-user daemon**, many projects. A :class:`ProjectRegistry` holds a
  warm :class:`~neuralmind.core.NeuralMind` per project path and a per-project
  lock, so concurrent build/query/watch on the same project serialize instead
  of corrupting the index or the synapse store (FR5).
- **A shared dispatch core** (:func:`dispatch`) maps ``(method, path, body)``
  to ``(status, payload)`` with no HTTP or transport knowledge. The HTTP
  handler is a thin wrapper over it; CLI and (later) MCP call the same
  contract, which is the point of the daemon boundary (FR3).
- **A** :class:`JobManager` runs builds in the background so a slow rebuild
  doesn't block the request, exposing pollable job status (FR4).
- **Discovery** is a per-user JSON file (host/port/token/pid); a client finds
  the daemon, and a stale file (dead pid / unreachable) is cleaned up so a
  crashed daemon never wedges the CLI.

Stdlib-only transport (``http.server`` on localhost, matching ``server.py``),
token-guarded even though it binds to loopback.
"""

from __future__ import annotations

import json
import os
import secrets
import signal
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8787
_STARTED_AT = time.time()


# --------------------------------------------------------------------------- #
# Discovery
# --------------------------------------------------------------------------- #


def discovery_path() -> Path:
    """Per-user daemon discovery file.

    Honors ``NEURALMIND_DAEMON_HOME`` (tests point it at a tmp dir) so a test
    daemon never clobbers a real one.
    """
    home = os.environ.get("NEURALMIND_DAEMON_HOME")
    base = Path(home) if home else Path.home() / ".neuralmind"
    return base / "daemon.json"


def write_discovery(info: dict, path: Path | None = None) -> Path:
    path = path or discovery_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(info, indent=2), encoding="utf-8")
    return path


def read_discovery(path: Path | None = None) -> dict | None:
    path = path or discovery_path()
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def clear_discovery(path: Path | None = None) -> None:
    path = path or discovery_path()
    try:
        path.unlink()
    except OSError:
        pass


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # exists, owned by someone else
    except OSError:
        return False
    return True


# --------------------------------------------------------------------------- #
# Project registry (warm cache + per-project locks)
# --------------------------------------------------------------------------- #


class ProjectRegistry:
    """Warm cache of NeuralMind instances keyed by absolute project path.

    ``mind_factory`` is injectable so tests can exercise the registry, locking,
    and dispatch without the embedding backend.
    """

    def __init__(self, mind_factory: Callable[[str], Any] | None = None) -> None:
        self._factory = mind_factory or self._default_factory
        self._minds: dict[str, Any] = {}
        self._locks: dict[str, threading.RLock] = {}
        self._built: set[str] = set()
        self._guard = threading.Lock()

    @staticmethod
    def _default_factory(project_path: str):
        from .core import NeuralMind

        return NeuralMind(project_path)

    @staticmethod
    def _key(project_path: str) -> str:
        # Canonicalize to a stable absolute key. os.path.abspath is pure-string
        # (no filesystem access), so a request-supplied project path doesn't
        # flow through a filesystem-touching sink here — the resolve()/read
        # happens later, behind validate_project's containment barrier and the
        # backend's own path handling.
        return os.path.abspath(project_path)

    def lock_for(self, project_path: str) -> threading.RLock:
        key = self._key(project_path)
        with self._guard:
            lock = self._locks.get(key)
            if lock is None:
                lock = threading.RLock()
                self._locks[key] = lock
            return lock

    def get(self, project_path: str):
        """Return the warm NeuralMind for a project, creating it once."""
        key = self._key(project_path)
        with self._guard:
            mind = self._minds.get(key)
            if mind is None:
                mind = self._factory(key)
                self._minds[key] = mind
            return mind

    def ensure_built(self, project_path: str) -> Any:
        """Get the project's mind, building its index once (warm thereafter)."""
        key = self._key(project_path)
        mind = self.get(key)
        with self.lock_for(key):
            if key not in self._built:
                if hasattr(mind, "build"):
                    mind.build()
                self._built.add(key)
        return mind

    def mark_unbuilt(self, project_path: str) -> None:
        self._built.discard(self._key(project_path))

    def projects(self) -> list[str]:
        with self._guard:
            return sorted(self._minds)

    def is_built(self, project_path: str) -> bool:
        return self._key(project_path) in self._built


# --------------------------------------------------------------------------- #
# Job manager (background builds)
# --------------------------------------------------------------------------- #

JOB_QUEUED = "queued"
JOB_RUNNING = "running"
JOB_DONE = "done"
JOB_ERROR = "error"


@dataclass
class Job:
    id: str
    kind: str
    project: str
    status: str = JOB_QUEUED
    result: dict | None = None
    error: str | None = None
    created_at: float = field(default_factory=time.time)
    finished_at: float | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "project": self.project,
            "status": self.status,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "finished_at": self.finished_at,
        }


class JobManager:
    """Runs jobs on background threads and tracks their status."""

    def __init__(self, max_jobs: int = 200) -> None:
        self._jobs: dict[str, Job] = {}
        self._order: list[str] = []
        self._guard = threading.Lock()
        self._max = max_jobs

    def submit(self, kind: str, project: str, fn: Callable[[], dict]) -> Job:
        job = Job(id=uuid.uuid4().hex[:12], kind=kind, project=project)
        with self._guard:
            self._jobs[job.id] = job
            self._order.append(job.id)
            self._evict_locked()
        threading.Thread(target=self._run, args=(job, fn), daemon=True).start()
        return job

    def _run(self, job: Job, fn: Callable[[], dict]) -> None:
        job.status = JOB_RUNNING
        try:
            job.result = fn()
            job.status = JOB_DONE
        except Exception as exc:  # surface failures as job state, never crash the daemon
            job.error = f"{type(exc).__name__}: {exc}"
            job.status = JOB_ERROR
        finally:
            job.finished_at = time.time()

    def get(self, job_id: str) -> Job | None:
        with self._guard:
            return self._jobs.get(job_id)

    def list(self) -> list[Job]:
        with self._guard:
            return [self._jobs[j] for j in self._order]

    def active_count(self) -> int:
        with self._guard:
            return sum(1 for j in self._jobs.values() if j.status in (JOB_QUEUED, JOB_RUNNING))

    def _evict_locked(self) -> None:
        while len(self._order) > self._max:
            old = self._order.pop(0)
            self._jobs.pop(old, None)


# --------------------------------------------------------------------------- #
# Shared dispatch core (transport-agnostic)
# --------------------------------------------------------------------------- #


@dataclass
class DaemonContext:
    registry: ProjectRegistry
    jobs: JobManager
    version: str = ""
    on_shutdown: Callable[[], None] | None = None


class DaemonError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


def _require(body: dict, key: str):
    val = body.get(key)
    if val in (None, ""):
        raise DaemonError(400, f"missing required field {key!r}")
    return val


def dispatch(ctx: DaemonContext, method: str, path: str, body: dict | None) -> tuple[int, dict]:
    """Map a request to ``(status_code, payload)`` with no transport knowledge.

    This is the single internal API contract the HTTP handler, the CLI client,
    and (later) the MCP server all speak — so behavior can't drift between
    surfaces (PRD 5 FR3).
    """
    parsed = urlparse(path)
    route = parsed.path.rstrip("/") or "/"
    qs = parse_qs(parsed.query)
    body = body or {}

    try:
        if method == "GET" and route == "/health":
            return 200, _health(ctx)
        if method == "GET" and route == "/status":
            return 200, _status(ctx)
        if method == "GET" and route == "/jobs":
            return 200, {"jobs": [j.to_dict() for j in ctx.jobs.list()]}
        if method == "GET" and route.startswith("/jobs/"):
            job = ctx.jobs.get(route.split("/jobs/", 1)[1])
            if job is None:
                raise DaemonError(404, "no such job")
            return 200, job.to_dict()
        if method == "GET" and route == "/stats":
            project = (qs.get("project") or [""])[0] or _require(body, "project")
            return 200, _stats(ctx, project)
        if method == "POST" and route == "/query":
            return 200, _query(
                ctx,
                _require(body, "project"),
                _require(body, "question"),
                trace=bool(body.get("trace", False)),
                trace_verbose=bool(body.get("trace_verbose", False)),
            )
        if method == "POST" and route == "/search":
            return 200, _search(
                ctx, _require(body, "project"), _require(body, "query"), int(body.get("n", 10))
            )
        if method == "POST" and route == "/build":
            return _build(
                ctx,
                _require(body, "project"),
                bool(body.get("force", False)),
                bool(body.get("sync", False)),
            )
        if method == "POST" and route == "/validate":
            return 200, _validate(ctx, _require(body, "project"), bool(body.get("write", False)))
        if method == "POST" and route == "/shutdown":
            if ctx.on_shutdown:
                ctx.on_shutdown()
            return 200, {"ok": True, "shutting_down": True}
        raise DaemonError(404, f"no route for {method} {route}")
    except DaemonError as exc:
        return exc.status, {"error": exc.message}
    except Exception as exc:  # never leak a traceback across the wire
        return 500, {"error": f"{type(exc).__name__}: {exc}"}


def _health(ctx: DaemonContext) -> dict:
    return {
        "ok": True,
        "status": "ready",
        "version": ctx.version,
        "pid": os.getpid(),
        "uptime_seconds": round(time.time() - _STARTED_AT, 1),
        "projects": ctx.registry.projects(),
        "jobs_active": ctx.jobs.active_count(),
    }


def _status(ctx: DaemonContext) -> dict:
    reg = ctx.registry
    return {
        **_health(ctx),
        "project_detail": [{"project": p, "built": reg.is_built(p)} for p in reg.projects()],
        "jobs": [j.to_dict() for j in ctx.jobs.list()],
    }


def _query(
    ctx: DaemonContext,
    project: str,
    question: str,
    trace: bool = False,
    trace_verbose: bool = False,
) -> dict:
    mind = ctx.registry.ensure_built(project)
    with ctx.registry.lock_for(project):
        result = mind.query(question, trace=trace, trace_verbose=trace_verbose)
    return {
        "project": project,
        "question": question,
        "tokens": getattr(getattr(result, "budget", None), "total", None),
        "reduction_ratio": round(getattr(result, "reduction_ratio", 0.0), 1),
        "layers": getattr(result, "layers_used", None),
        "context": getattr(result, "context", ""),
        "trace": getattr(result, "trace", None),
    }


def _search(ctx: DaemonContext, project: str, query: str, n: int) -> dict:
    mind = ctx.registry.ensure_built(project)
    with ctx.registry.lock_for(project):
        results = mind.search(query, n=n)
    return {"project": project, "query": query, "results": results}


def _stats(ctx: DaemonContext, project: str) -> dict:
    mind = ctx.registry.get(project)
    with ctx.registry.lock_for(project):
        return mind.get_stats()


def _build(ctx: DaemonContext, project: str, force: bool, sync: bool) -> tuple[int, dict]:
    def _do() -> dict:
        mind = ctx.registry.get(project)
        with ctx.registry.lock_for(project):
            result = mind.build(force=force)
        ctx.registry.mark_unbuilt(project)  # re-mark so ensure_built is a no-op
        ctx.registry._built.add(ctx.registry._key(project))
        return result

    if sync:
        return 200, _do()
    job = ctx.jobs.submit("build", project, _do)
    return 202, {"job_id": job.id, "status": job.status}


def _validate(ctx: DaemonContext, project: str, write: bool) -> dict:
    # Backend-free: validate_project never touches the embedding engine.
    from .core import validate_project

    return validate_project(project, write=write)


# --------------------------------------------------------------------------- #
# HTTP transport
# --------------------------------------------------------------------------- #


class _Handler(BaseHTTPRequestHandler):
    # Context and token live on the *server instance* (set in create_server),
    # never as class attributes — so multiple daemons in one process (e.g. the
    # test suite) can't clobber each other's state.

    def log_message(self, *args) -> None:  # silence default stderr spam
        pass

    @property
    def _ctx(self) -> DaemonContext:
        return self.server.nm_context  # type: ignore[attr-defined]

    def _authed(self) -> bool:
        token = self.server.nm_token  # type: ignore[attr-defined]
        if token is None:
            return True
        header = self.headers.get("Authorization", "")
        if header.startswith("Bearer "):
            return secrets.compare_digest(header[7:], token)
        qtoken = (parse_qs(urlparse(self.path).query).get("token") or [""])[0]
        return bool(qtoken) and secrets.compare_digest(qtoken, token)

    def _send(self, status: int, payload: dict) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _handle(self, method: str) -> None:
        if not self._authed():
            self._send(401, {"error": "missing or invalid token"})
            return
        body = {}
        if method == "POST":
            length = int(self.headers.get("Content-Length", 0) or 0)
            if length:
                try:
                    body = json.loads(self.rfile.read(length).decode("utf-8"))
                except ValueError:
                    self._send(400, {"error": "invalid JSON body"})
                    return
        status, payload = dispatch(self._ctx, method, self.path, body)
        self._send(status, payload)

    def do_GET(self) -> None:  # noqa: N802
        self._handle("GET")

    def do_POST(self) -> None:  # noqa: N802
        self._handle("POST")


def create_server(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    *,
    auth: bool = True,
    registry: ProjectRegistry | None = None,
    write_disco: bool = True,
) -> tuple[ThreadingHTTPServer, dict]:
    """Bind the daemon socket and attach its state, *without* serving yet.

    The socket is bound + listening on return (TCPServer does both in
    ``__init__``), so a caller can start ``serve_forever`` in a thread and
    clients connect reliably with no startup race. State (context + token) is
    attached to the server instance, so multiple daemons never share state.
    Returns ``(httpd, info)``; the caller owns shutdown.
    """
    from . import __version__

    registry = registry or ProjectRegistry()
    jobs = JobManager()
    token = secrets.token_urlsafe(16) if auth else None

    httpd = ThreadingHTTPServer((host, port), _Handler)
    httpd.daemon_threads = True
    actual_port = httpd.server_address[1]

    httpd.nm_context = DaemonContext(  # type: ignore[attr-defined]
        registry=registry,
        jobs=jobs,
        version=__version__,
        on_shutdown=lambda: threading.Thread(target=httpd.shutdown, daemon=True).start(),
    )
    httpd.nm_token = token  # type: ignore[attr-defined]

    info = {
        "host": host,
        "port": actual_port,
        "token": token,
        "pid": os.getpid(),
        "version": __version__,
        "started_at": time.time(),
    }
    if write_disco:
        write_discovery(info)
    return httpd, info


def serve(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    *,
    auth: bool = True,
    registry: ProjectRegistry | None = None,
) -> None:
    """Run the daemon in the foreground until shutdown (blocking)."""
    httpd, info = create_server(host, port, auth=auth, registry=registry)

    def _graceful(*_a) -> None:
        threading.Thread(target=httpd.shutdown, daemon=True).start()

    # signal handlers only register on the main thread; running the daemon from
    # a worker thread (e.g. tests) silently skips them rather than crashing.
    if threading.current_thread() is threading.main_thread():
        signal.signal(signal.SIGTERM, _graceful)
        signal.signal(signal.SIGINT, _graceful)

    print(
        f"[neuralmind] daemon listening on http://{info['host']}:{info['port']} "
        f"(pid {os.getpid()})"
    )
    try:
        httpd.serve_forever()
    finally:
        clear_discovery()
        httpd.server_close()


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(prog="neuralmind-daemon")
    ap.add_argument("--host", default=DEFAULT_HOST)
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--no-auth", action="store_true", help="disable the loopback token (tests)")
    args = ap.parse_args(argv)
    serve(args.host, args.port, auth=not args.no_auth)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
