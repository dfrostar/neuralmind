"""
server.py — Local graph-view UI for NeuralMind.

``neuralmind serve`` starts a stdlib HTTP server that renders the code
graph (structural edges from graph.json) with the learned synapse
overlay on top. Obsidian-style: force-directed graph, backlinks panel,
local graph, community browser, and semantic quick-switch search.

No external dependencies, no CDN — the frontend is vanilla JS served
from ``neuralmind/web/``. The HTTP handlers themselves are read-only,
but ``serve()`` calls ``mind.build()`` on startup, which writes/updates
the embedding index under ``graphify-out/neuralmind_db/`` — same
side-effects as ``neuralmind build``.
"""

from __future__ import annotations

import json
import os
import secrets
import shlex
import shutil
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .core import NeuralMind

WEB_DIR = Path(__file__).parent / "web"

_CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
}

_AUTH_COOKIE = "nm_token"


def _build_graph_payload(mind: NeuralMind) -> dict:
    """Materialize the graph payload once; the graph is static per session."""
    data = mind.graph_data()
    counts: dict[int, int] = {}
    for node in data["nodes"]:
        cid = node.get("community", -1)
        counts[cid] = counts.get(cid, 0) + 1
    data["communities"] = [{"id": cid, "size": size} for cid, size in sorted(counts.items())]
    return data


def _search(mind: NeuralMind, query: str, n: int = 12) -> list[dict]:
    if not query:
        return []
    try:
        hits = mind.search(query, n=n)
    except Exception:
        return []
    results = []
    for hit in hits:
        meta = hit.get("metadata", {})
        results.append(
            {
                "id": str(hit.get("id", "")),
                "label": meta.get("label", hit.get("id", "")),
                "source_file": meta.get("source_file", ""),
                "community": meta.get("community", -1),
                "score": round(float(hit.get("score", 0.0)), 3),
            }
        )
    return results


def _editor_command(editor: str, path: str, line: int | None) -> list[str]:
    """Build the argv for opening ``path`` at ``line`` in ``editor``.

    Respects the user's $EDITOR (split with shlex so values like
    ``"code -n"`` work) and chooses a sensible jump-to-line flag for
    well-known editors. Unknown editors get the path with no line.
    """
    # shlex defaults to POSIX rules, which strip backslashes — that
    # mangles Windows paths like ``C:\Program Files\...\code.exe``.
    # Fall back to the non-POSIX tokenizer on Windows so those keep working.
    parts = shlex.split(editor, posix=(os.name != "nt")) if editor else []
    if not parts:
        return []
    name = Path(parts[0]).name.lower()
    base = parts
    if name in {"code", "code-insiders", "codium", "vscodium", "cursor", "windsurf"}:
        target = f"{path}:{line}" if line else path
        return base + ["--goto", target]
    if name in {"vim", "nvim", "vi", "nano", "emacs", "emacsclient"}:
        return base + ([f"+{line}", path] if line else [path])
    if name in {"subl", "sublime_text"}:
        return base + ([f"{path}:{line}"] if line else [path])
    if name == "idea" or name.startswith("idea") or name == "pycharm":
        return base + (["--line", str(line), path] if line else [path])
    return base + [path]


def _resolve_open_target(mind: NeuralMind, node_id: str) -> tuple[Path | None, int | None, str]:
    """Map a node id to (absolute file path under project, line, label).

    Returns ``(None, None, reason)`` if the node is unknown, has no
    source file, or the resolved path escapes the project root.
    """
    nodes = getattr(mind.embedder, "nodes", []) or []
    node = next((n for n in nodes if str(n.get("id")) == node_id), None)
    if node is None:
        return None, None, "unknown node id"

    src = node.get("source_file") or ""
    if not src:
        return None, None, "node has no source file"

    project_root = Path(mind.project_path).resolve()
    candidate = Path(src)
    if not candidate.is_absolute():
        candidate = project_root / candidate
    try:
        resolved = candidate.resolve()
    except Exception:
        return None, None, "could not resolve source file"

    try:
        resolved.relative_to(project_root)
    except ValueError:
        return None, None, "source file is outside the project root"

    if not resolved.is_file():
        return None, None, f"file does not exist: {resolved}"

    # Defense in depth: resolve() always returns an absolute path, but we
    # still want to be loud if that ever stops being true — and an absolute
    # path can't start with '-', which is what would make Popen treat it
    # as an editor flag rather than a filename.
    if not resolved.is_absolute() or str(resolved).startswith("-"):
        return None, None, "refusing to open suspicious path"

    loc = str(node.get("source_location") or "")
    line: int | None = None
    if loc:
        try:
            line = int(loc.lstrip("Ll"))
        except ValueError:
            line = None

    return resolved, line, node.get("label", node_id)


class _Handler(BaseHTTPRequestHandler):
    # Set by serve() before the server starts; shared across threads.
    mind: NeuralMind | None = None
    auth_token: str | None = None  # None disables auth
    editor: str | None = None
    _graph_cache: dict | None = None
    _graph_lock = threading.Lock()

    def log_message(self, *args):  # noqa: D102 - silence default request logging
        pass

    def _graph(self) -> dict:
        cls = type(self)
        with cls._graph_lock:
            if cls._graph_cache is None:
                cls._graph_cache = _build_graph_payload(cls.mind)
            return cls._graph_cache

    def _check_auth(self, parsed) -> tuple[bool, str | None]:
        """Return (allowed, new_cookie_value).

        The token may arrive via ?token= (first visit, becomes a cookie)
        or as the persisted cookie on subsequent requests. When auth is
        disabled, everything is allowed.
        """
        cls = type(self)
        if cls.auth_token is None:
            return True, None

        cookie_header = self.headers.get("Cookie", "")
        cookies = {}
        for piece in cookie_header.split(";"):
            piece = piece.strip()
            if "=" in piece:
                k, v = piece.split("=", 1)
                cookies[k.strip()] = v.strip()
        if cookies.get(_AUTH_COOKIE) == cls.auth_token:
            return True, None

        query_token = (parse_qs(parsed.query).get("token") or [None])[0]
        if query_token and secrets.compare_digest(query_token, cls.auth_token):
            return True, cls.auth_token

        return False, None

    def _send_json(self, payload: dict, status: int = 200, set_cookie: str | None = None) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        if set_cookie:
            self.send_header(
                "Set-Cookie",
                f"{_AUTH_COOKIE}={set_cookie}; Path=/; HttpOnly; SameSite=Strict",
            )
        self.end_headers()
        self.wfile.write(body)

    def _send_static(self, name: str, set_cookie: str | None = None) -> None:
        path = (WEB_DIR / name).resolve()
        if not str(path).startswith(str(WEB_DIR.resolve())) or not path.is_file():
            self.send_error(404)
            return
        body = path.read_bytes()
        self.send_response(200)
        self.send_header(
            "Content-Type",
            _CONTENT_TYPES.get(path.suffix, "application/octet-stream"),
        )
        self.send_header("Content-Length", str(len(body)))
        if set_cookie:
            self.send_header(
                "Set-Cookie",
                f"{_AUTH_COOKIE}={set_cookie}; Path=/; HttpOnly; SameSite=Strict",
            )
        self.end_headers()
        self.wfile.write(body)

    def _deny(self, route: str) -> None:
        if route in ("/", "/index.html"):
            # Friendlier landing page than a raw 401.
            body = (
                b"<!doctype html><meta charset=utf-8>"
                b"<title>NeuralMind</title>"
                b"<style>body{font-family:system-ui;background:#1a1b1e;"
                b"color:#d6d7da;padding:48px;line-height:1.5}</style>"
                b"<h1>NeuralMind graph view</h1>"
                b"<p>This URL is missing the access token. Re-open the link "
                b"printed by <code>neuralmind serve</code> "
                b"(it ends with <code>?token=&hellip;</code>), or pass "
                b"<code>--no-auth</code> when starting the server."
            )
            self.send_response(401)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(401, "missing or invalid token")

    def _read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return {}

    def do_GET(self) -> None:  # noqa: N802 - http.server API
        parsed = urlparse(self.path)
        route = parsed.path
        ok, new_cookie = self._check_auth(parsed)
        if not ok:
            self._deny(route)
            return

        if route in ("/", "/index.html"):
            self._send_static("index.html", set_cookie=new_cookie)
        elif route in ("/app.js", "/style.css"):
            self._send_static(route.lstrip("/"), set_cookie=new_cookie)
        elif route == "/api/graph":
            self._send_json(self._graph(), set_cookie=new_cookie)
        elif route == "/api/search":
            query = (parse_qs(parsed.query).get("q") or [""])[0].strip()
            self._send_json(
                {"query": query, "results": _search(type(self).mind, query)},
                set_cookie=new_cookie,
            )
        else:
            self.send_error(404)

    def do_POST(self) -> None:  # noqa: N802 - http.server API
        parsed = urlparse(self.path)
        route = parsed.path
        ok, new_cookie = self._check_auth(parsed)
        if not ok:
            self._deny(route)
            return

        if route == "/api/open":
            body = self._read_json_body()
            node_id = str(body.get("id") or "")
            cls = type(self)
            path, line, label = _resolve_open_target(cls.mind, node_id)
            if path is None:
                self._send_json(
                    {"ok": False, "error": label},
                    status=400,
                    set_cookie=new_cookie,
                )
                return

            editor = cls.editor
            if not editor:
                self._send_json(
                    {
                        "ok": False,
                        "error": "no editor configured (set $EDITOR or use --editor)",
                        "file": str(path),
                        "line": line,
                    },
                    status=400,
                    set_cookie=new_cookie,
                )
                return

            argv = _editor_command(editor, str(path), line)
            if not argv or not shutil.which(argv[0]):
                self._send_json(
                    {
                        "ok": False,
                        "error": f"editor not found on PATH: {argv[0] if argv else editor}",
                        "file": str(path),
                        "line": line,
                    },
                    status=400,
                    set_cookie=new_cookie,
                )
                return

            try:
                subprocess.Popen(  # noqa: S603 - argv list, no shell
                    argv,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    close_fds=True,
                )
            except OSError as exc:
                self._send_json(
                    {"ok": False, "error": f"failed to launch editor: {exc}"},
                    status=500,
                    set_cookie=new_cookie,
                )
                return

            self._send_json(
                {"ok": True, "file": str(path), "line": line, "label": label},
                set_cookie=new_cookie,
            )
        else:
            self.send_error(404)


def _ensure_graph_or_explain(project_path: Path) -> None:
    """Raise a user-friendly error when graphify hasn't run yet.

    Without this the build call surfaces a terse "Could not load graph
    from ..." message that doesn't tell first-time users what to do.
    """
    graph_path = project_path / "graphify-out" / "graph.json"
    if graph_path.exists():
        return
    msg = (
        f"no graph found at {graph_path}\n"
        f"\n"
        f"NeuralMind needs a graphify build first. To generate one:\n"
        f"  pip install graphifyy        # if not already installed\n"
        f"  graphify update {project_path}\n"
        f"\n"
        f"Then re-run: neuralmind serve {project_path}"
    )
    raise RuntimeError(msg)


def serve(
    project_path: str,
    host: str = "127.0.0.1",
    port: int = 8765,
    open_browser: bool = True,
    auth: bool = True,
    editor: str | None = None,
) -> None:
    """Build the index and serve the graph-view UI until interrupted."""
    project_path = Path(project_path).resolve()
    _ensure_graph_or_explain(project_path)

    mind = NeuralMind(str(project_path))
    build = mind.build()
    if not build.get("success"):
        raise RuntimeError(build.get("error", "build failed"))

    token = secrets.token_urlsafe(16) if auth else None
    _Handler.mind = mind
    _Handler.auth_token = token
    _Handler.editor = editor or os.environ.get("EDITOR") or os.environ.get("VISUAL")
    _Handler._graph_cache = None

    httpd = ThreadingHTTPServer((host, port), _Handler)
    base = f"http://{host}:{port}/"
    landing = f"{base}?token={token}" if token else base
    stats = mind.graph_data()["stats"]
    print(f"NeuralMind graph view: {landing}")
    print(
        f"  {stats['nodes']} nodes · {stats['edges']} structural edges · "
        f"{stats['synapses']} learned synapses"
    )
    if _Handler.editor:
        print(f"  Editor: {_Handler.editor}")
    else:
        print("  Editor: not set (clicks to open will be no-ops; set $EDITOR)")
    if token:
        print("  Access token required. Share the URL above to re-open this session.")
    print("  Ctrl-C to stop.")

    if open_browser:
        try:
            import webbrowser

            webbrowser.open(landing)
        except Exception:
            pass

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping NeuralMind graph view.")
    finally:
        httpd.server_close()
