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

from . import backends, judge
from .backends import BackendResult, RepoFiles
from .tokens import tokenizer_name

MANIFEST = Path(__file__).with_name("manifest.json")
DEFAULT_WORK_DIR = Path(".bench-work")
BACKEND_ORDER = ["full-file", "ripgrep", "embedding-rag", "neuralmind"]


def load_manifest(path: str | Path = MANIFEST) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _git(args: list[str], timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(args, check=True, capture_output=True, text=True, timeout=timeout)


def _head(dest: Path) -> str | None:
    try:
        return _git(["git", "-C", str(dest), "rev-parse", "HEAD"], timeout=30).stdout.strip()
    except (subprocess.SubprocessError, OSError):
        return None


def _checkout_pinned(dest: Path, commit: str) -> bool:
    """Fetch + checkout an exact commit in an existing clone. False on failure."""
    try:
        _git(["git", "-C", str(dest), "fetch", "--depth", "1", "origin", commit], timeout=180)
        _git(["git", "-C", str(dest), "checkout", commit], timeout=60)
        return _head(dest) == commit
    except (subprocess.SubprocessError, OSError):
        return False


def ensure_checkout(repo: dict[str, Any], work_dir: Path) -> Path | None:
    """Return the repo's source dir, pinned to ``repo['commit']``.

    Clones the pinned commit if absent, and — critically for reproducibility —
    **verifies an already-present checkout is at the pinned SHA**, re-pinning it
    if a prior/stale run left it elsewhere. Returns ``None`` (never raises) when
    the checkout can't be produced *or can't be confirmed at the pinned commit*,
    so we never benchmark a stale tree while advertising the pinned SHA.
    """
    dest = work_dir / repo["name"]
    src = dest / repo.get("subdir", "")
    commit = repo.get("commit")
    if src.exists():
        # Reuse only if it's verifiably the pinned commit; otherwise re-pin it.
        if not commit or _head(dest) == commit:
            return src
        return src if (_checkout_pinned(dest, commit) and src.exists()) else None
    work_dir.mkdir(parents=True, exist_ok=True)
    try:
        _git(
            ["git", "clone", "--depth", "1", "--branch", repo["tag"], repo["url"], str(dest)],
            timeout=180,
        )
    except (subprocess.SubprocessError, OSError):
        return None
    # Pin exactly: if the tag didn't resolve to the committed SHA, re-pin.
    if commit and _head(dest) != commit and not _checkout_pinned(dest, commit):
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


def run_repo(
    repo: dict[str, Any], work_dir: Path, seeds: int = 1, judge_client: Any | None = None
) -> dict[str, Any] | None:
    """Run every backend over every query for one repo. ``None`` if skipped.

    When ``judge_client`` is provided, the opt-in answerability arm also runs:
    each backend's *real* window text is answered + graded (see
    ``evals/public/judge.py``). This is off the deterministic path — the recall
    numbers above are byte-identical with or without the arm."""
    src = ensure_checkout(repo, work_dir)
    if src is None:
        return {"name": repo["name"], "skipped": "checkout unavailable (no network?)"}
    repo_files = RepoFiles.load(src)
    nm = _build_nm(src)
    arm = judge.JudgeArm(judge_client) if judge_client is not None else None
    by_backend: dict[str, list[BackendResult]] = {b: [] for b in BACKEND_ORDER}
    rows: list[dict[str, Any]] = []
    for query in repo["queries"]:
        qresults = run_query(query, repo_files, nm)
        for r in qresults:
            by_backend[r.backend].append(r)
        rows.append(
            {"query_id": query["id"], "results": {r.backend: r.to_dict() for r in qresults}}
        )
        if arm is not None:
            arm.judge_query(query, qresults)
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
        # Answerability arm (only when --judge ran); a clearly-labeled secondary
        # signal, never folded into the recall headline above.
        **({"judge_summary": arm.summary(), "judge_raw": arm.raw} if arm is not None else {}),
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
    judge_client: Any | None = None,
) -> dict[str, Any]:
    # Determinism is a hard requirement for a reproducible public number, so we
    # pin synapse injection OFF *unconditionally*: synapse weights are
    # session/usage-dependent (they learn from how *you* work), so they cannot
    # belong in a fixed public benchmark. We override (not setdefault) any
    # caller's NEURALMIND_SYNAPSE_INJECT so a stray `=1` in the shell/CI can't
    # silently make the published number user-specific, and restore it after.
    # The synapse *learning* lift is measured separately by the synapse A/B eval
    # (`tests/benchmark/run.py` Phase 2) and the onboarding eval.
    prior_inject = os.environ.get("NEURALMIND_SYNAPSE_INJECT")
    os.environ["NEURALMIND_SYNAPSE_INJECT"] = "0"
    try:
        repos = [r for r in manifest["repos"] if (only is None or r["name"] == only)]
        return {
            "tokenizer": tokenizer_name(),
            "oracle": manifest.get("oracle", "def-site"),
            "synapse_injection": "0",
            "backends": BACKEND_ORDER,
            "repos": [run_repo(r, work_dir, seeds, judge_client) for r in repos],
        }
    finally:
        if prior_inject is None:
            os.environ.pop("NEURALMIND_SYNAPSE_INJECT", None)
        else:
            os.environ["NEURALMIND_SYNAPSE_INJECT"] = prior_inject


# --------------------------------------------------------------------------- #
# Report rendering
# --------------------------------------------------------------------------- #


def _ratio_phrase(full_tokens: float, backend_tokens: float) -> str:
    """Honest "Nx fewer/more" wording — never claims "fewer" when it's actually more."""
    if not backend_tokens:
        return "—"
    factor = full_tokens / backend_tokens
    if factor >= 1.05:
        return f"{factor:.1f}× fewer"
    if factor <= 0.95:
        return f"{1 / factor:.1f}× more"
    return "≈ same"


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
                ratio = f"  ({_ratio_phrase(full['mean_tokens'], s['mean_tokens'])})"
            out.append(
                f"| `{b}` | {s['mean_recall']:.2f} | {s['found_rate']:.0%} "
                f"| {s['mean_tokens']:.0f}{ratio} | {s['mean_mrr']:.2f} |"
            )
        out.append("")
        # The honest headline: NeuralMind's recall at its cost vs. the naive ceiling.
        nm_s = repo["summary"].get("neuralmind")
        if nm_s and full.get("mean_tokens") and nm_s.get("mean_tokens"):
            out.append(
                f"**Headline:** NeuralMind reaches **{nm_s['mean_recall']:.0%} gold-file recall** "
                f"at **{_ratio_phrase(full['mean_tokens'], nm_s['mean_tokens'])} tokens** than "
                f"pasting every file (which is recall 1.0 by definition, at full cost).\n"
            )
        judge_summary = repo.get("judge_summary")
        if judge_summary:
            out.append("### Answerability (LLM-judged — *secondary signal*)\n")
            out.append(
                "_Not the headline. Each backend is judged on its **real window** "
                f"(whole files / chunks / compact context) by `{judge.JUDGE_MODEL}`, "
                "answering from that context only. Published prompts + raw transcripts: "
                "`bench/public/judge/`._\n"
            )
            out.append("| backend | mean score | answered-rate | grounded-rate |")
            out.append("|---|---:|---:|---:|")
            for b in report["backends"]:
                js = judge_summary.get(b)
                if not js:
                    continue
                out.append(
                    f"| `{b}` | {js['mean_score']:.2f} | {js['answered_rate']:.0%} "
                    f"| {js['grounded_rate']:.0%} |"
                )
            out.append("")
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
        elif repo.get("retrieval_stack_available"):
            out.append("_No NeuralMind gold-file misses on this repo._\n")
        else:
            # NeuralMind never ran here — don't claim a clean sweep it didn't earn.
            out.append("_NeuralMind not evaluated (retrieval stack unavailable); no miss data._\n")
    return "\n".join(out)


def _write_judge_transcripts(report: dict[str, Any], out_dir: Path) -> None:
    """Commit the answerability arm's raw per-query transcripts + a summary.

    Provenance the docs point skeptics at: every (question, context tokens,
    answer, verdict, rationale) plus the pinned judge model id."""
    raw_dir = out_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for repo in report.get("repos", []):
        raw = repo.get("judge_raw")
        if not raw:
            continue
        (raw_dir / f"{repo['name']}.json").write_text(
            json.dumps(raw, indent=2) + "\n", encoding="utf-8"
        )
        rows.append(
            {
                "name": repo["name"],
                "commit": repo.get("commit"),
                "judge_model": judge.JUDGE_MODEL,
                "summary": repo.get("judge_summary", {}),
            }
        )
    (out_dir / "results.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    print(f"wrote answerability transcripts under {out_dir}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="NeuralMind honest public benchmark")
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON to stdout")
    ap.add_argument("--repo", default=None, help="run a single repo by name")
    ap.add_argument("--seeds", type=int, default=1, help="seed count (pipeline is deterministic)")
    ap.add_argument(
        "--work-dir", default=str(DEFAULT_WORK_DIR), help="where pinned repos are cloned"
    )
    ap.add_argument("--out", default=None, help="write results.json + report.md under this dir")
    ap.add_argument(
        "--judge",
        action="store_true",
        help="also run the opt-in LLM-judged answerability arm (needs ANTHROPIC_API_KEY)",
    )
    ap.add_argument(
        "--judge-out",
        default="bench/public/judge",
        help="where to write answerability transcripts (with --judge)",
    )
    args = ap.parse_args(argv)

    judge_client = None
    if args.judge:
        judge_client = judge.make_client()
        if judge_client is None:
            print(
                "--judge needs ANTHROPIC_API_KEY and the `anthropic` package; "
                "skipping the answerability arm (the recall table still runs).",
                file=sys.stderr,
            )

    manifest = load_manifest()
    report = run_all(
        manifest, Path(args.work_dir), only=args.repo, seeds=args.seeds, judge_client=judge_client
    )

    if judge_client is not None:
        _write_judge_transcripts(report, Path(args.judge_out))

    if args.out:
        out_dir = Path(args.out)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        (out_dir / "report.md").write_text(render_markdown(report), encoding="utf-8")
        print(f"wrote {out_dir / 'results.json'} and {out_dir / 'report.md'}", file=sys.stderr)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(render_markdown(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
