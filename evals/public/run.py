"""Run the honest public benchmark and emit a reproducible report.

    python -m evals.public.run                # build report from the manifest
    python -m evals.public.run --json         # machine-readable to stdout
    python -m evals.public.run --repo requests --seeds 3

For each pinned repo + pre-registered query, every backend assembles context;
we score **gold-file recall** (deterministic, no LLM) against **token cost** and
roll it up into a cost/correctness frontier. Repos are cloned at their pinned
commit on demand; if the network or retrieval stack is unavailable the run skips
that repo cleanly (never a traceback) so the harness stays CI-safe.

The headline number is never a lone reduction ratio: it is "equal-or-better
recall at N× fewer tokens," and every query — including losses — is reported.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import statistics
import subprocess
import sys
from pathlib import Path
from typing import Any

from . import backends
from .backends import BackendResult, RepoFiles
from .tokens import tokenizer_name

MANIFEST = Path(__file__).with_name("manifest.json")
DEFAULT_WORK_DIR = Path(".bench-work")
BACKEND_ORDER = ["full-file", "ripgrep", "embedding-rag", "neuralmind"]


def load_manifest(path: str | Path = MANIFEST) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def ensure_checkout(repo: dict[str, Any], work_dir: Path) -> Path | None:
    """Return the repo's source dir, cloning the pinned commit if needed.

    Returns ``None`` (never raises) when the checkout can't be produced — e.g.
    no network — so the caller can skip the repo cleanly.
    """
    dest = work_dir / repo["name"]
    src = dest / repo.get("subdir", "")
    if src.exists():
        return src
    work_dir.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", "--branch", repo["tag"], repo["url"], str(dest)],
            check=True,
            capture_output=True,
            timeout=180,
        )
        # Pin exactly: verify the tag resolved to the committed SHA.
        head = subprocess.run(
            ["git", "-C", str(dest), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        ).stdout.strip()
        if repo.get("commit") and head != repo["commit"]:
            # Tag moved or mismatch — fetch the exact pinned commit.
            subprocess.run(
                ["git", "-C", str(dest), "fetch", "--depth", "1", "origin", repo["commit"]],
                check=True,
                capture_output=True,
                timeout=180,
            )
            subprocess.run(
                ["git", "-C", str(dest), "checkout", repo["commit"]],
                check=True,
                capture_output=True,
                timeout=60,
            )
    except (subprocess.SubprocessError, OSError):
        return None
    return src if src.exists() else None


def _build_nm(src: Path) -> Any | None:
    """Build a NeuralMind index for ``src``; ``None`` if the stack is unavailable."""
    try:
        from neuralmind.core import NeuralMind

        with contextlib.redirect_stdout(sys.stderr):
            nm = NeuralMind(str(src))
            build = nm.build()
            if not build.get("success", True):
                return None
        return nm
    except Exception:
        return None


def run_query(query: dict[str, Any], repo_files: RepoFiles, nm: Any) -> list[BackendResult]:
    """All backends for one query (deterministic; identical across seeds)."""
    qid = query["id"]
    gold = query["gold_files"]
    q = query["question"]
    results = [
        backends.run_full_file(qid, gold, repo_files),
        backends.run_ripgrep(qid, q, gold, repo_files),
    ]
    if nm is not None:
        results.append(backends.run_embedding_rag(qid, q, gold, nm))
        results.append(backends.run_neuralmind(qid, q, gold, nm))
    return results


def _aggregate(per_query: list[BackendResult]) -> dict[str, Any]:
    """Backend-level summary over its per-query results."""
    recalls = [r.recall for r in per_query]
    toks = [r.tokens for r in per_query]
    return {
        "n": len(per_query),
        "mean_recall": round(statistics.mean(recalls), 4) if recalls else 0.0,
        "found_rate": (
            round(sum(r.found for r in per_query) / len(per_query), 4) if per_query else 0.0
        ),
        "mean_tokens": round(statistics.mean(toks), 1) if toks else 0.0,
        "median_tokens": round(statistics.median(toks), 1) if toks else 0.0,
        "mean_mrr": (
            round(statistics.mean([r.reciprocal_rank for r in per_query]), 4) if per_query else 0.0
        ),
    }


def run_repo(repo: dict[str, Any], work_dir: Path, seeds: int = 1) -> dict[str, Any] | None:
    """Run every backend over every query for one repo. ``None`` if skipped."""
    src = ensure_checkout(repo, work_dir)
    if src is None:
        return {"name": repo["name"], "skipped": "checkout unavailable (no network?)"}
    repo_files = RepoFiles.load(src)
    nm = _build_nm(src)
    by_backend: dict[str, list[BackendResult]] = {b: [] for b in BACKEND_ORDER}
    rows: list[dict[str, Any]] = []
    for query in repo["queries"]:
        qresults = run_query(query, repo_files, nm)
        for r in qresults:
            by_backend[r.backend].append(r)
        rows.append(
            {"query_id": query["id"], "results": {r.backend: r.to_dict() for r in qresults}}
        )
    summary = {b: _aggregate(rs) for b, rs in by_backend.items() if rs}
    return {
        "name": repo["name"],
        "commit": repo.get("commit"),
        "language": repo.get("language"),
        "n_queries": len(repo["queries"]),
        "retrieval_stack_available": nm is not None,
        # The pipeline is deterministic, so variance across seeds is exactly 0.
        # We record the seed count honestly rather than inject artificial noise.
        "seeds": seeds,
        "summary": summary,
        "queries": rows,
        "losses": [
            {"query_id": q["query_id"], "backend": b, **r}
            for q in rows
            for b, r in q["results"].items()
            if b == "neuralmind" and not r["found"]
        ],
    }


def run_all(
    manifest: dict[str, Any],
    work_dir: Path = DEFAULT_WORK_DIR,
    only: str | None = None,
    seeds: int = 1,
) -> dict[str, Any]:
    # Determinism is a hard requirement for a reproducible public number, so we
    # pin synapse injection OFF: synapse weights are session/usage-dependent
    # (they learn from how *you* work), so they cannot belong in a fixed public
    # benchmark anyway. The synapse *learning* lift is measured separately by the
    # synapse A/B eval (`tests/benchmark/run.py` Phase 2) and onboarding eval.
    os.environ.setdefault("NEURALMIND_SYNAPSE_INJECT", "0")
    repos = [r for r in manifest["repos"] if (only is None or r["name"] == only)]
    return {
        "tokenizer": tokenizer_name(),
        "oracle": manifest.get("oracle", "def-site"),
        "synapse_injection": os.environ.get("NEURALMIND_SYNAPSE_INJECT", "0"),
        "backends": BACKEND_ORDER,
        "repos": [run_repo(r, work_dir, seeds) for r in repos],
    }


# --------------------------------------------------------------------------- #
# Report rendering
# --------------------------------------------------------------------------- #


def render_markdown(report: dict[str, Any]) -> str:
    out: list[str] = []
    out.append("# NeuralMind — honest public benchmark\n")
    out.append(
        "Cost (context tokens) vs. correctness (**gold-file recall**, the objective "
        "def-site oracle — no LLM judge) across pinned real repositories. Every query "
        "is reported, including losses. Reproduce with `python -m evals.public.run`.\n"
    )
    out.append(f"- **Tokenizer:** {report['tokenizer']}")
    out.append(
        "- **Determinism:** synapse injection OFF, so every backend's numbers "
        "reproduce exactly. The synapse *learning* lift is session-dependent and "
        "measured separately by the synapse A/B eval — not part of this fixed number."
    )
    out.append(f"- **Correctness oracle:** {report['oracle']} (gold = symbol definition site)")
    out.append(
        "- **Baselines:** `full-file` (paste every file), `ripgrep` (keyword → top files), "
        "`embedding-rag` (top-k chunks, same encoder), `neuralmind` (progressive disclosure + synapses)\n"
    )
    for repo in report["repos"]:
        out.append(f"## {repo['name']}  `@{(repo.get('commit') or '')[:10]}`\n")
        if repo.get("skipped"):
            out.append(f"_Skipped: {repo['skipped']}_\n")
            continue
        if not repo.get("retrieval_stack_available"):
            out.append(
                "_Retrieval stack unavailable in this environment — only the file-based "
                "baselines ran. Rerun where the embedding stack is installed for the full matrix._\n"
            )
        out.append(
            f"{repo['n_queries']} pre-registered queries · "
            f"retrieval stack: {'yes' if repo.get('retrieval_stack_available') else 'no'}\n"
        )
        out.append("| backend | gold-file recall | found-rate | mean tokens/query | MRR |")
        out.append("|---|---:|---:|---:|---:|")
        full = repo["summary"].get("full-file", {})
        for b in report["backends"]:
            s = repo["summary"].get(b)
            if not s:
                continue
            ratio = ""
            if b != "full-file" and full.get("mean_tokens") and s.get("mean_tokens"):
                ratio = f"  ({full['mean_tokens'] / s['mean_tokens']:.1f}× fewer)"
            out.append(
                f"| `{b}` | {s['mean_recall']:.2f} | {s['found_rate']:.0%} "
                f"| {s['mean_tokens']:.0f}{ratio} | {s['mean_mrr']:.2f} |"
            )
        out.append("")
        # The honest headline: NeuralMind's recall at its cost vs. the naive ceiling.
        nm_s = repo["summary"].get("neuralmind")
        if nm_s and full.get("mean_tokens"):
            factor = full["mean_tokens"] / nm_s["mean_tokens"] if nm_s["mean_tokens"] else 0
            out.append(
                f"**Headline:** NeuralMind reaches **{nm_s['mean_recall']:.0%} gold-file recall** "
                f"at **{factor:.0f}× fewer tokens** than pasting every file "
                f"(which is recall 1.0 by definition, at full cost).\n"
            )
        losses = repo.get("losses", [])
        if losses:
            out.append("### Where NeuralMind loses\n")
            out.append("| query | gold | retrieved files |")
            out.append("|---|---|---|")
            for ls in losses:
                out.append(
                    f"| `{ls['query_id']}` | {', '.join(ls['gold_files'])} "
                    f"| {', '.join(ls['context_files'][:6]) or '—'} |"
                )
            out.append("")
        else:
            out.append("_No NeuralMind gold-file misses on this repo._\n")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="NeuralMind honest public benchmark")
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON to stdout")
    ap.add_argument("--repo", default=None, help="run a single repo by name")
    ap.add_argument("--seeds", type=int, default=1, help="seed count (pipeline is deterministic)")
    ap.add_argument(
        "--work-dir", default=str(DEFAULT_WORK_DIR), help="where pinned repos are cloned"
    )
    ap.add_argument("--out", default=None, help="write results.json + report.md under this dir")
    args = ap.parse_args(argv)

    manifest = load_manifest()
    report = run_all(manifest, Path(args.work_dir), only=args.repo, seeds=args.seeds)

    if args.out:
        out_dir = Path(args.out)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        (out_dir / "report.md").write_text(render_markdown(report), encoding="utf-8")
        print(f"wrote {out_dir/'results.json'} and {out_dir/'report.md'}", file=sys.stderr)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(render_markdown(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
