#!/usr/bin/env python3
"""benchmark_turbovec.py — TurboVec vs. ChromaDB memory/latency benchmark.

Answers the v0.21.0 release-notes follow-up:

    "A large-synthetic-repo memory/latency benchmark is a follow-up."

It runs the two backends exposed by ``neuralmind.backend_manager.create_backend``
(``chroma`` and ``turbovec``) against the *same* graph, on the *same* machine,
with *identical* queries, and measures indexing latency, search latency
(p50/p95/mean, per query type), on-disk index size, peak RSS, and Python-side
peak allocation (tracemalloc). It also records each backend's top-k result ids
so ``report_turbovec.py`` can compute query-level parity (Jaccard / recall).

Process isolation
-----------------
Each backend runs in its *own* ``spawn``-context subprocess (this same file
re-invoked with ``--_worker``), so:

* chroma's transitive import tree (FastAPI, kubernetes client, OpenTelemetry,
  grpcio, …) never inflates the turbovec memory measurement;
* a crash in one backend doesn't tank the other;
* ``getrusage(RUSAGE_SELF).ru_maxrss`` reads the per-process high-water mark
  cleanly (normalised KB-on-Linux / bytes-on-macOS → MB before reporting).

The parent process builds the synthetic repo and the shared ``graph.json``
once; the workers only ``load_graph`` → ``embed_nodes`` → ``search``.

Usage
-----
    # Synthetic 600-file repo, no setup, cleaned up afterwards:
    python benchmark_turbovec.py --out results.json

    # Your own repo (first run needs a graph; --build generates one):
    python benchmark_turbovec.py --repo ~/code/my-project --build --out results.json
    # Subsequent runs (graph already at graphify-out/graph.json):
    python benchmark_turbovec.py --repo ~/code/my-project --out results.json

Then render the Markdown report:

    python report_turbovec.py results.json --out report.md
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import resource
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

# The parent process must be able to *generate* a synthetic repo and a
# graph.json without importing the heavy backend stacks. Keep these imports
# lazy / local to the worker where they're actually needed.

SCRIPT = Path(__file__).resolve()

# --------------------------------------------------------------------------- #
# Default query set
# --------------------------------------------------------------------------- #
# Topic-aligned with the synthetic repo's module themes (see THEMES below) so
# the queries actually retrieve something meaningful, while still reading like
# natural-language code questions. For a real --repo these are generic enough
# to exercise the index even if they don't all hit.
DEFAULT_QUERIES: list[str] = [
    "how does user authentication and login work",
    "validate and sanitize incoming request payloads",
    "open and manage a database connection pool",
    "cache expensive results with a time-to-live",
    "parse and serialize JSON configuration",
    "schedule a recurring background job",
    "retry an HTTP request with exponential backoff",
    "compute a checksum or hash of a file",
    "log structured events for observability",
    "handle errors and raise a domain-specific exception",
]

# --------------------------------------------------------------------------- #
# Synthetic repo generation (parent process, stdlib only)
# --------------------------------------------------------------------------- #
THEMES: list[tuple[str, str, list[str]]] = [
    # (package, docstring topic, verbs)
    (
        "auth",
        "user authentication, login, tokens and sessions",
        ["authenticate", "login", "logout", "issue_token", "verify_session"],
    ),
    (
        "validation",
        "validating and sanitizing incoming request payloads",
        ["validate", "sanitize", "coerce", "check_schema", "normalize_input"],
    ),
    (
        "db",
        "database connections, pooling and transactions",
        ["connect", "acquire_connection", "release", "begin_transaction", "execute_query"],
    ),
    (
        "cache",
        "caching expensive results with a time-to-live",
        ["cache_get", "cache_set", "evict", "with_ttl", "invalidate"],
    ),
    (
        "config",
        "parsing and serializing JSON/YAML configuration",
        ["load_config", "dump_config", "merge_config", "parse_json", "serialize"],
    ),
    (
        "scheduler",
        "scheduling recurring background jobs",
        ["schedule", "tick", "enqueue_job", "run_periodic", "cancel_job"],
    ),
    (
        "http",
        "HTTP requests with retries and exponential backoff",
        ["fetch", "retry_request", "backoff", "build_url", "decode_response"],
    ),
    (
        "hashing",
        "computing checksums and hashes of files",
        ["checksum", "hash_file", "digest", "verify_integrity", "fingerprint"],
    ),
    (
        "logging",
        "structured logging and observability events",
        ["log_event", "emit_metric", "trace", "with_context", "redact"],
    ),
    (
        "errors",
        "domain-specific exceptions and error handling",
        ["raise_domain_error", "wrap_exception", "handle", "is_retryable", "to_dict"],
    ),
]


def _gen_file(theme_idx: int, file_idx: int) -> str:
    package, topic, verbs = THEMES[theme_idx % len(THEMES)]
    cls = f"{package.capitalize()}Service{file_idx}"
    lines = [
        f'"""{package}.module{file_idx} — {topic}."""',
        "",
        "from __future__ import annotations",
        "",
        "import hashlib",
        "import json",
        "import time",
        "",
        "",
        f"class {cls}:",
        f'    """Handles {topic} (variant {file_idx})."""',
        "",
        "    def __init__(self, config: dict | None = None) -> None:",
        "        self.config = config or {}",
        "        self._cache: dict[str, object] = {}",
        "",
    ]
    for v in verbs:
        lines += [
            f"    def {v}(self, payload: dict) -> dict:",
            f'        """{v.replace("_", " ").capitalize()} — part of {topic}."""',
            "        key = json.dumps(payload, sort_keys=True)",
            "        digest = hashlib.sha256(key.encode()).hexdigest()",
            "        self._cache[digest] = time.time()",
            '        return {"ok": True, "op": "' + v + '", "digest": digest}',
            "",
        ]
    # A module-level helper to create call/import edges within the package.
    lines += [
        "",
        f"def make_{package}_service(config: dict | None = None) -> {cls}:",
        f'    """Factory for :class:`{cls}` ({topic})."""',
        f"    return {cls}(config)",
        "",
    ]
    return "\n".join(lines)


def generate_synthetic_repo(root: Path, n_files: int) -> int:
    """Create ``n_files`` themed Python modules under ``root``. Returns count."""
    root.mkdir(parents=True, exist_ok=True)
    per_theme = max(1, n_files // len(THEMES))
    written = 0
    for theme_idx, (package, _topic, _verbs) in enumerate(THEMES):
        pkg_dir = root / package
        pkg_dir.mkdir(parents=True, exist_ok=True)
        (pkg_dir / "__init__.py").write_text(f'"""The {package} package."""\n', encoding="utf-8")
        for file_idx in range(per_theme):
            if written >= n_files:
                break
            (pkg_dir / f"module{file_idx}.py").write_text(
                _gen_file(theme_idx, file_idx), encoding="utf-8"
            )
            written += 1
    # Top up to exactly n_files if integer division left a remainder.
    extra = 0
    while written < n_files:
        theme_idx = extra % len(THEMES)
        package = THEMES[theme_idx][0]
        (root / package / f"extra{extra}.py").write_text(
            _gen_file(theme_idx, 1000 + extra), encoding="utf-8"
        )
        written += 1
        extra += 1
    return written


def build_graph_json(repo: Path) -> dict:
    """Generate ``graphify-out/graph.json`` via the built-in tree-sitter graph.

    Mirrors ``neuralmind.core.NeuralMind._generate_graph`` without pulling in a
    backend. Returns ``{"nodes": int, "links": int}``.
    """
    from neuralmind import graphgen

    if not graphgen.is_available():
        raise RuntimeError(
            "the built-in graph backend needs tree-sitter — "
            "`pip install tree-sitter tree-sitter-python` (bundled with neuralmind)."
        )
    graph = graphgen.build_graph(repo)
    out_dir = repo / "graphify-out"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "graph.json").write_text(json.dumps(graph, indent=2), encoding="utf-8")
    return {"nodes": len(graph.get("nodes", [])), "links": len(graph.get("links", []))}


def count_source_files(repo: Path) -> int:
    exts = {".py", ".ts", ".go"}
    return sum(
        1
        for p in repo.rglob("*")
        if p.is_file()
        and p.suffix in exts
        and ".neuralmind" not in p.parts
        and "graphify-out" not in p.parts
    )


# --------------------------------------------------------------------------- #
# Worker (runs in an isolated spawn subprocess; imports the heavy backend)
# --------------------------------------------------------------------------- #
def _dir_size_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size
    total = 0
    for p in path.rglob("*"):
        try:
            if p.is_file():
                total += p.stat().st_size
        except OSError:
            continue
    return total


def _peak_rss_mb() -> float:
    """Per-process high-water RSS via getrusage, normalised to MB.

    ``ru_maxrss`` is KB on Linux, bytes on macOS — normalise both to MB.
    """
    ru = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform == "darwin":
        return ru / (1024 * 1024)
    return ru / 1024


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    rank = (pct / 100.0) * (len(s) - 1)
    lo = int(rank)
    hi = min(lo + 1, len(s) - 1)
    frac = rank - lo
    return s[lo] + (s[hi] - s[lo]) * frac


def run_worker(backend: str, cfg: dict, result_path: Path) -> None:
    """Index + query a single backend, writing a result JSON to ``result_path``."""
    import tracemalloc

    import psutil  # noqa: F401  (per the docs: fail loudly here if missing)

    from neuralmind.backend_manager import create_backend

    repo = cfg["repo"]
    queries: list[str] = cfg["queries"]
    top_k: int = cfg["top_k"]
    warmup: int = cfg["warmup"]
    repeat: int = cfg["repeat"]
    db_path = cfg["db_paths"][backend]

    proc = psutil.Process(os.getpid())
    result: dict = {"backend": backend, "ok": False}

    tracemalloc.start()
    try:
        be = create_backend(backend, repo, db_path)

        if not be.load_graph():
            raise RuntimeError("load_graph() returned False — no graph.json?")

        t0 = time.perf_counter()
        embed_stats = be.embed_nodes(force=True)
        index_sec = time.perf_counter() - t0

        try:
            stats = be.get_stats()
        except Exception:
            stats = {}

        # Warm-up (model into RAM, caches primed) — not measured.
        for q in queries[: max(1, len(queries))]:
            for _ in range(warmup):
                be.search(q, n=top_k)

        per_query: list[dict] = []
        all_latencies: list[float] = []
        for q in queries:
            latencies: list[float] = []
            top_ids: list[str] = []
            for r in range(repeat):
                s = time.perf_counter()
                res = be.search(q, n=top_k)
                latencies.append((time.perf_counter() - s) * 1000.0)
                if r == 0:
                    top_ids = [str(item.get("id")) for item in res]
            all_latencies.extend(latencies)
            per_query.append(
                {
                    "query": q,
                    "top_ids": top_ids,
                    "ms_p50": _percentile(latencies, 50),
                    "ms_p95": _percentile(latencies, 95),
                    "ms_mean": statistics.fmean(latencies) if latencies else 0.0,
                }
            )

        _cur, py_peak = tracemalloc.get_traced_memory()

        try:
            be.close()
        except Exception:
            pass

        result.update(
            {
                "ok": True,
                "index_seconds": index_sec,
                "embed_stats": embed_stats,
                "stats": stats,
                "disk_bytes": _dir_size_bytes(Path(db_path)),
                "peak_rss_mb": _peak_rss_mb(),
                "rss_now_mb": proc.memory_info().rss / (1024 * 1024),
                "tracemalloc_peak_mb": py_peak / (1024 * 1024),
                "search": {
                    "ms_p50": _percentile(all_latencies, 50),
                    "ms_p95": _percentile(all_latencies, 95),
                    "ms_mean": statistics.fmean(all_latencies) if all_latencies else 0.0,
                    "n_samples": len(all_latencies),
                },
                "per_query": per_query,
            }
        )
    except Exception as exc:  # report failure rather than crash the run
        import traceback

        result.update({"ok": False, "error": str(exc), "traceback": traceback.format_exc()})
    finally:
        tracemalloc.stop()

    result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")


# --------------------------------------------------------------------------- #
# Environment provenance (parent process)
# --------------------------------------------------------------------------- #
def _pkg_version(name: str) -> str | None:
    try:
        from importlib.metadata import PackageNotFoundError, version

        try:
            return version(name)
        except PackageNotFoundError:
            return None
    except Exception:
        return None


def collect_environment(repo: Path, source_files: int, graph: dict) -> dict:
    return {
        "neuralmind": _pkg_version("neuralmind"),
        "turbovec": _pkg_version("turbovec"),
        "chromadb": _pkg_version("chromadb"),
        "onnxruntime": _pkg_version("onnxruntime"),
        "tokenizers": _pkg_version("tokenizers"),
        "numpy": _pkg_version("numpy"),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu_count": os.cpu_count(),
        "repo": str(repo),
        "source_files": source_files,
        "graph_nodes": graph.get("nodes"),
        "graph_links": graph.get("links"),
    }


# --------------------------------------------------------------------------- #
# Parent orchestration
# --------------------------------------------------------------------------- #
def spawn_backend(backend: str, cfg: dict, work_dir: Path) -> dict:
    """Run one backend in an isolated subprocess and return its result dict."""
    cfg_path = work_dir / f"cfg_{backend}.json"
    res_path = work_dir / f"result_{backend}.json"
    cfg_path.write_text(json.dumps(cfg), encoding="utf-8")

    env = dict(os.environ)
    # Force spawn semantics regardless of platform default; the worker is a
    # fresh interpreter so module-level state never leaks between backends.
    cmd = [
        sys.executable,
        str(SCRIPT),
        "--_worker",
        backend,
        "--_cfg",
        str(cfg_path),
        "--_result",
        str(res_path),
    ]
    print(f"  → spawning isolated worker for backend={backend!r} …")
    completed = subprocess.run(cmd, env=env)
    if res_path.exists():
        result = json.loads(res_path.read_text(encoding="utf-8"))
    else:
        result = {
            "backend": backend,
            "ok": False,
            "error": f"worker produced no result (exit code {completed.returncode})",
        }
    if not result.get("ok"):
        print(f"    ! backend {backend!r} failed: {result.get('error', 'unknown')}")
    else:
        print(
            f"    ✓ {backend}: index {result['index_seconds']:.2f}s, "
            f"search p50 {result['search']['ms_p50']:.2f}ms, "
            f"disk {result['disk_bytes'] / 1e6:.1f}MB, "
            f"peak RSS {result['peak_rss_mb']:.1f}MB"
        )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--out", default="results.json", help="output JSON path")
    parser.add_argument("--repo", default=None, help="path to a real repo (>=500 source files)")
    parser.add_argument(
        "--build", action="store_true", help="generate graph.json via tree-sitter for --repo"
    )
    parser.add_argument(
        "--files", type=int, default=600, help="synthetic repo file count (default 600)"
    )
    parser.add_argument("--keep-repo", action="store_true", help="don't delete the synthetic repo")
    parser.add_argument("--top-k", type=int, default=10, help="results per query (default 10)")
    parser.add_argument(
        "--repeat", type=int, default=20, help="timed repeats per query (default 20)"
    )
    parser.add_argument("--warmup", type=int, default=2, help="warm-up runs per query (default 2)")
    parser.add_argument(
        "--backends",
        default="chroma,turbovec",
        help="comma-separated backends to compare (default chroma,turbovec)",
    )
    parser.add_argument(
        "--queries-file", default=None, help="newline-delimited query file (overrides defaults)"
    )

    # Hidden worker entrypoint — re-invoked per backend in an isolated process.
    parser.add_argument("--_worker", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--_cfg", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--_result", default=None, help=argparse.SUPPRESS)

    args = parser.parse_args(argv)

    if args._worker:
        cfg = json.loads(Path(args._cfg).read_text(encoding="utf-8"))
        run_worker(args._worker, cfg, Path(args._result))
        return 0

    # Ensure the parent can import the local neuralmind package.
    sys.path.insert(0, str(SCRIPT.parent))

    queries = DEFAULT_QUERIES
    if args.queries_file:
        queries = [
            line.strip()
            for line in Path(args.queries_file).read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    backends = [b.strip() for b in args.backends.split(",") if b.strip()]

    # ---- Repo + graph setup ------------------------------------------------ #
    synthetic = args.repo is None
    if synthetic:
        repo = Path(f"/tmp/nm_bench_repo_{os.getpid()}")
        print(f"Generating synthetic repo ({args.files} files) at {repo} …")
        n = generate_synthetic_repo(repo, args.files)
        print(f"  wrote {n} files")
        graph = build_graph_json(repo)
        print(f"  built graph.json: {graph['nodes']} nodes, {graph['links']} links")
    else:
        repo = Path(args.repo).resolve()
        if not repo.is_dir():
            print(f"--repo not a directory: {repo}", file=sys.stderr)
            return 2
        src = count_source_files(repo)
        if src < 500:
            print(
                f"WARNING: {repo} has only {src} source files (.py/.ts/.go); "
                "the benchmark is designed for >=500.",
                file=sys.stderr,
            )
        graph_path = repo / "graphify-out" / "graph.json"
        if args.build or not graph_path.exists():
            print("Building graph.json via tree-sitter …")
            graph = build_graph_json(repo)
            print(f"  built graph.json: {graph['nodes']} nodes, {graph['links']} links")
        else:
            g = json.loads(graph_path.read_text(encoding="utf-8"))
            graph = {"nodes": len(g.get("nodes", [])), "links": len(g.get("links", []))}
            print(f"Using existing graph.json: {graph['nodes']} nodes, {graph['links']} links")

    source_files = count_source_files(repo)

    work_dir = Path(f"/tmp/nm_bench_work_{os.getpid()}")
    work_dir.mkdir(parents=True, exist_ok=True)

    # Separate db path per backend so they never share state.
    db_paths = {b: str(repo / "graphify-out" / f"bench_db_{b}") for b in backends}
    cfg = {
        "repo": str(repo),
        "queries": queries,
        "top_k": args.top_k,
        "warmup": args.warmup,
        "repeat": args.repeat,
        "db_paths": db_paths,
    }

    print(f"\nBenchmarking backends: {', '.join(backends)}")
    print(
        f"  queries={len(queries)} top_k={args.top_k} repeat={args.repeat} warmup={args.warmup}\n"
    )

    results: dict[str, dict] = {}
    for backend in backends:
        results[backend] = spawn_backend(backend, cfg, work_dir)

    payload = {
        "schema": "neuralmind-turbovec-benchmark/1",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "config": {
            "top_k": args.top_k,
            "repeat": args.repeat,
            "warmup": args.warmup,
            "synthetic": synthetic,
            "queries": queries,
            "backends": backends,
        },
        "environment": collect_environment(repo, source_files, graph),
        "results": results,
    }

    out = Path(args.out)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\nWrote {out}")

    # ---- Cleanup ----------------------------------------------------------- #
    try:
        shutil.rmtree(work_dir)
    except OSError:
        pass
    if synthetic and not args.keep_repo:
        try:
            shutil.rmtree(repo)
            print(f"Cleaned up synthetic repo {repo}")
        except OSError:
            pass
    elif synthetic:
        print(f"Kept synthetic repo at {repo}")

    ok = all(r.get("ok") for r in results.values())
    print("\nNext: python report_turbovec.py", str(out), "--out report.md")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
