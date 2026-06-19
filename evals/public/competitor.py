"""Live, reproducible head-to-head vs. ``codebase-memory-mcp`` (DeusData).

The competitor runs **headless with no LLM API key** — on-device embeddings, a
single-binary CLI. We index a pinned repo checkout with it, then for each
benchmark question issue its ``search_graph`` semantic query and project the
returned ``semantic_results[].file_path`` to gold-file basenames, scored by the
**same** ``neuralmind.quality`` gold-file-recall code every other backend uses.

Fairness (see ``docs/prd/competitor-benchmark.md``):

- The competitor's semantic interface takes a **keyword array**, not free text.
  We compared three reproducible mappings and use the one *most favorable to the
  competitor* (all question words — see ``competitor_keywords``), so the result
  can't be dismissed as crippling it. No per-query hand-tuning.
- We pin the exact competitor version, use its documented CLI verbatim, and
  commit the raw per-query JSON traces.

This is a **separate entrypoint**, not part of ``python -m evals.public.run`` (the
public CI table must never depend on an external binary download): run it with
``python -m evals.public.competitor``. It fails closed (clean skip) when the
binary isn't installed.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from .backends import BackendResult, RepoFiles
from .tokens import count_tokens


def competitor_keywords(question: str) -> list[str]:
    """Keyword array for the competitor's semantic interface — *every* word of
    the question (no stopword filtering).

    The competitor takes a keyword array, not free text. We compared three
    reproducible strategies (ripgrep's ``_keywords``, the whole question as one
    string, and all words) and use **all words**, which scored *best for the
    competitor* on the corpus — so the comparison gives it its most favorable
    reproducible input and can't be dismissed as crippling it."""
    return re.findall(r"[A-Za-z_][A-Za-z0-9_]+", question.lower())


# Pin the exact competitor version this row was produced against (probed live).
COMPETITOR_BIN = "codebase-memory-mcp"
COMPETITOR_PINNED_VERSION = "0.8.1"
# Its semantic search returns a separate ranked list capped by ``sem_limit``;
# 8 is a typical retrieval depth (matched to RAG_TOP_K in the baseline matrix).
SEM_LIMIT = 8


def installed_version() -> str | None:
    """The installed competitor version, or ``None`` if the binary is absent."""
    try:
        out = subprocess.run(
            [COMPETITOR_BIN, "--version"],
            check=True,
            capture_output=True,
            text=True,
            timeout=120,  # first run may download the binary from GitHub Releases
        )
    except (subprocess.SubprocessError, OSError):
        return None
    # e.g. "codebase-memory-mcp 0.8.1"
    parts = out.stdout.split()
    return parts[-1].strip() if parts else None


def _cli(args: list[str], cache_dir: Path, timeout: int = 240) -> dict[str, Any] | None:
    """Run a competitor CLI tool and return its **unwrapped** JSON result.

    The CLI wraps tool output as ``{"content":[{"type":"text","text":"<json>"}]}``;
    we parse the inner JSON. Returns ``None`` on any failure (fail-closed)."""
    env = {**os.environ, "CBM_CACHE_DIR": str(cache_dir)}
    try:
        out = subprocess.run(
            [COMPETITOR_BIN, "cli", "--json", *args],
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        raw = json.loads(out.stdout)
    except (subprocess.SubprocessError, OSError, ValueError):
        return None
    return _unwrap(raw)


def _unwrap(raw: dict[str, Any]) -> dict[str, Any] | None:
    """Unwrap the MCP ``content[0].text`` JSON envelope (or pass a bare dict).

    Returns ``None`` for an **error envelope** (``isError`` true) so a failed tool
    call fails closed — never accepted as a result that could query a stale
    cached project."""
    if not isinstance(raw, dict):
        return None
    if raw.get("isError"):
        return None
    content = raw.get("content")
    if isinstance(content, list) and content:
        text = content[0].get("text") if isinstance(content[0], dict) else None
        if isinstance(text, str):
            try:
                inner = json.loads(text)
            except ValueError:
                return None
            # The inner payload can also carry an error/status even when the
            # envelope didn't flag it — reject those too.
            if isinstance(inner, dict) and (inner.get("error") or inner.get("status") == "error"):
                return None
            return inner
    return raw  # already-unwrapped shape (defensive)


def index_repo(repo_dir: str | Path, cache_dir: Path) -> str | None:
    """Index ``repo_dir`` with the competitor; return its project name (or None).

    Requires a confirmed ``status == "indexed"`` and a project name — a partial
    or errored index never returns a name the query path could reuse stale."""
    result = _cli(
        ["index_repository", json.dumps({"repo_path": str(Path(repo_dir).resolve())})],
        cache_dir,
    )
    if not result or result.get("status") != "indexed":
        return None
    return result.get("project")


def semantic_files(project: str, keywords: list[str], cache_dir: Path) -> list[str]:
    """Ranked file basenames for a keyword query (strongest score first)."""
    if not keywords:
        return []
    result = _cli(
        [
            "search_graph",
            json.dumps({"project": project, "semantic_query": keywords, "sem_limit": SEM_LIMIT}),
        ],
        cache_dir,
    )
    if not result:
        return []
    ranked = result.get("semantic_results") or result.get("results") or []
    # Cap at the retrieval depth BEFORE projecting to files — exactly parallel to
    # the embedding-rag baseline (top-k chunks → their files), so recall@k, MRR,
    # and cost are apples-to-apples. The tool may return a longer list; scoring
    # over an uncapped list would meaninglessly inflate recall.
    files: list[str] = []
    seen: set[str] = set()
    for r in ranked[:SEM_LIMIT]:
        fp = r.get("file_path")
        if not fp:
            continue
        name = Path(str(fp)).name
        if name not in seen:
            seen.add(name)
            files.append(name)
    return files


def run_competitor(
    query_id: str,
    question: str,
    gold_files: list[str],
    project: str,
    repo: RepoFiles,
    cache_dir: Path,
) -> BackendResult:
    """One competitor answer for one query, scored like every other backend.

    Keywords are all question words (the competitor's most favorable reproducible
    mapping); cost is a disclosed proxy — the tokens of the distinct whole files
    the competitor surfaces at its retrieval depth (it returns file paths the
    agent then opens, analogous to how ripgrep is costed)."""
    keywords = competitor_keywords(question)
    files = semantic_files(project, keywords, cache_dir)
    tokens = sum(count_tokens(repo.texts[f]) for f in files if f in repo.texts)
    return BackendResult("competitor", query_id, gold_files, files, tokens)


# --------------------------------------------------------------------------- #
# Suite runner (off the default path — external binary, not CI-gated)
# --------------------------------------------------------------------------- #


def run_repo(repo: dict[str, Any], work_dir: Path, cache_dir: Path) -> dict[str, Any]:
    """Index one pinned repo with the competitor and score every query."""
    from . import run as public_run  # lazy: avoids a cycle at import time

    src = public_run.ensure_checkout(repo, work_dir)
    if src is None:
        return {"name": repo["name"], "skipped": "checkout unavailable"}
    repo_files = RepoFiles.load(src)
    project = index_repo(src, cache_dir)
    if not project:
        return {"name": repo["name"], "skipped": "competitor indexing failed"}
    results: list[BackendResult] = []
    raw: list[dict[str, Any]] = []
    for q in repo["queries"]:
        keywords = competitor_keywords(q["question"])
        r = run_competitor(q["id"], q["question"], q["gold_files"], project, repo_files, cache_dir)
        results.append(r)
        raw.append(
            {
                "query_id": q["id"],
                "question": q["question"],
                "keywords": keywords,
                "gold_files": q["gold_files"],
                "ranked_files": r.context_files,
                "found": r.found,
                "recall": round(r.recall, 4),
            }
        )
    summary = public_run._aggregate(results)
    return {
        "name": repo["name"],
        "commit": repo.get("commit"),
        "competitor_version": installed_version(),
        "n_queries": len(repo["queries"]),
        "summary": summary,
        "raw": raw,
    }


def main(argv: list[str] | None = None) -> int:
    import argparse

    from . import run as public_run

    ap = argparse.ArgumentParser(description="codebase-memory-mcp head-to-head")
    ap.add_argument("--repo", default=None, help="single corpus repo by name")
    ap.add_argument("--work-dir", default=str(public_run.DEFAULT_WORK_DIR))
    ap.add_argument("--out", default="bench/public/competitor", help="where to write raw traces")
    args = ap.parse_args(argv)

    version = installed_version()
    if version is None:
        print(
            f"{COMPETITOR_BIN} is not installed. Install it (pins {COMPETITOR_PINNED_VERSION}) "
            "and re-run — see bench/public/competitor/REPRODUCE.md.",
        )
        return 2
    if version != COMPETITOR_PINNED_VERSION:
        print(f"warning: installed competitor {version} != pinned {COMPETITOR_PINNED_VERSION}")

    work_dir = Path(args.work_dir)
    cache_dir = work_dir / "cbm-cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    manifest = public_run.load_manifest()
    repos = [r for r in manifest["repos"] if (args.repo is None or r["name"] == args.repo)]

    out_dir = Path(args.out)
    (out_dir / "raw").mkdir(parents=True, exist_ok=True)
    rows = []
    for repo in repos:
        res = run_repo(repo, work_dir, cache_dir)
        rows.append(res)
        if "raw" in res:
            (out_dir / "raw" / f"{res['name']}.json").write_text(
                json.dumps(res["raw"], indent=2) + "\n", encoding="utf-8"
            )
        s = res.get("summary")
        if s:
            print(
                f"{res['name']}: recall={s['mean_recall']:.2f} found={s['found_rate']:.0%} "
                f"mean_tokens={s['mean_tokens']:.0f} (competitor {res.get('competitor_version')})"
            )
        else:
            print(f"{res['name']}: {res.get('skipped')}")
    (out_dir / "results.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out_dir/'results.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
