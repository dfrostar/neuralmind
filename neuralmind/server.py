"""
server.py — Local graph-view UI for NeuralMind.

``neuralmind serve`` starts a stdlib HTTP server that renders the code
graph (structural edges from graph.json) with the learned synapse
overlay on top. Obsidian-style: force-directed graph, backlinks panel,
local graph, community browser, and semantic quick-switch search.

No external dependencies, no CDN — the frontend is vanilla JS served
from ``neuralmind/web/``. Everything runs against the existing index and
``.neuralmind/synapses.db``; the server is read-only and never writes.
"""

from __future__ import annotations

import json
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


def _build_graph_payload(mind: NeuralMind) -> dict:
    """Materialize the graph payload once; the graph is static per session."""
    data = mind.graph_data()
    counts: dict[int, int] = {}
    for node in data["nodes"]:
        cid = node.get("community", -1)
        counts[cid] = counts.get(cid, 0) + 1
    data["communities"] = [
        {"id": cid, "size": size} for cid, size in sorted(counts.items())
    ]
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


class _Handler(BaseHTTPRequestHandler):
    # Set by serve() before the server starts; shared across threads.
    mind: NeuralMind | None = None
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

    def _send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_static(self, name: str) -> None:
        path = (WEB_DIR / name).resolve()
        # Guard against path traversal — only serve files inside web/.
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
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - http.server API
        parsed = urlparse(self.path)
        route = parsed.path

        if route in ("/", "/index.html"):
            self._send_static("index.html")
        elif route in ("/app.js", "/style.css"):
            self._send_static(route.lstrip("/"))
        elif route == "/api/graph":
            self._send_json(self._graph())
        elif route == "/api/search":
            query = (parse_qs(parsed.query).get("q") or [""])[0].strip()
            self._send_json(
                {"query": query, "results": _search(type(self).mind, query)}
            )
        else:
            self.send_error(404)


def serve(
    project_path: str,
    host: str = "127.0.0.1",
    port: int = 8765,
    open_browser: bool = True,
) -> None:
    """Build the index and serve the graph-view UI until interrupted."""
    mind = NeuralMind(str(project_path))
    build = mind.build()
    if not build.get("success"):
        raise RuntimeError(build.get("error", "build failed"))

    _Handler.mind = mind
    _Handler._graph_cache = None

    httpd = ThreadingHTTPServer((host, port), _Handler)
    url = f"http://{host}:{port}/"
    stats = mind.graph_data()["stats"]
    print(f"NeuralMind graph view: {url}")
    print(
        f"  {stats['nodes']} nodes · {stats['edges']} structural edges · "
        f"{stats['synapses']} learned synapses"
    )
    print("  Ctrl-C to stop.")

    if open_browser:
        try:
            import webbrowser

            webbrowser.open(url)
        except Exception:
            pass

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping NeuralMind graph view.")
    finally:
        httpd.server_close()
