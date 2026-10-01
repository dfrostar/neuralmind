"""Multi-repo retrieval eval: does a ranking change earn its place? (spec 7)

    python -m evals.retrieval.run                          # public repos + this one
    python -m evals.retrieval.run --private ~/work/app     # add a private repo (local only)
    python -m evals.retrieval.run --configs baseline,per_file --out bench/retrieval
    python -m evals.retrieval.run --public-benchmark       # also re-run evals.public per config

Every v4.6.0 ranking change sits behind a flag. This harness runs the
pre-registered questions in ``evals/retrieval/questions/`` (30 per repo,
written before any change was tried) once per flag configuration, read-only,
and applies the keep rule from the spec:

* mean hit@5 across repos goes up, and it goes up on at least 3 repos;
* no repo drops by more than one question;
* average context tokens rise by at most 10%;
* the public 4-repo benchmark's gold-file recall doesn't drop
  (``--public-benchmark``).

Repos: requests, click, flask and rich at the public benchmark's pinned
commits (cloned on demand), plus this repository. ``--private PATH`` adds a
repository whose questions live in its own ``.neuralmind.eval.yaml``; it is
copied to the work dir (so its own ``.neuralmind/`` is never touched) and
reported only in aggregate, as ``private``.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
QUESTIONS = Path(__file__).with_name("questions")
MANIFEST = REPO_ROOT / "evals" / "public" / "manifest.json"

FLAGS = (
    "NEURALMIND_L3_PER_FILE",
    "NEURALMIND_DOC_HANDOFF",
    "NEURALMIND_HUB_DAMPEN",
    "NEURALMIND_BM25_CODE",
    "NEURALMIND_BM25",
    "NEURALMIND_INTENT_RULES",
)

# One configuration per work item, the all-on combination, and the BM25-off
# comparison spec 7 item 5 asks for before building anything new.
CONFIGS: dict[str, dict[str, str]] = {
    "baseline": {},
    "per_file": {"NEURALMIND_L3_PER_FILE": "2"},
    "handoff": {"NEURALMIND_DOC_HANDOFF": "1"},
    "hub": {"NEURALMIND_HUB_DAMPEN": "1"},
    "code_bm25": {"NEURALMIND_BM25_CODE": "1"},
    "bm25_off": {"NEURALMIND_BM25": "0"},
    "intent": {"NEURALMIND_INTENT_RULES": "1"},
    "all": {
        "NEURALMIND_L3_PER_FILE": "2",
        "NEURALMIND_DOC_HANDOFF": "1",
        "NEURALMIND_HUB_DAMPEN": "1",
        "NEURALMIND_BM25_CODE": "1",
        "NEURALMIND_INTENT_RULES": "1",
    },
}

MIN_REPOS_IMPROVED = 3
MAX_DROP_QUESTIONS = 1
MAX_TOKEN_RISE = 0.10


# --------------------------------------------------------------------------- #
# Preparing repositories
# --------------------------------------------------------------------------- #
def _git(*args: str, timeout: int = 300) -> str:
    return subprocess.run(
        ["git", *args], check=True, capture_output=True, text=True, timeout=timeout
    ).stdout


def _pinned_clone(work: Path, repo: dict[str, Any]) -> Path:
    dest = work / repo["name"]
    if not (dest / ".git").exists():
        dest.mkdir(parents=True, exist_ok=True)
        _git("init", "-q", str(dest))
        _git("-C", str(dest), "remote", "add", "origin", repo["url"])
    head = ""
    try:
        head = _git("-C", str(dest), "rev-parse", "HEAD").strip()
    except subprocess.CalledProcessError:
        pass
    if head != repo["commit"]:
        _git("-C", str(dest), "fetch", "-q", "--depth", "1", "origin", repo["commit"])
        _git("-C", str(dest), "checkout", "-q", repo["commit"])
    return dest / (repo.get("subdir") or "")


def _copy_git_visible(src: Path, dest: Path) -> Path:
    """Copy the files git covers (tracked + untracked-not-ignored) to ``dest``."""
    if dest.exists():
        shutil.rmtree(dest)
    files = _git(
        "-C", str(src), "ls-files", "-z", "--cached", "--others", "--exclude-standard"
    ).split("\0")
    for rel in filter(None, files):
        s = src / rel
        if s.is_file():
            d = dest / rel
            d.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(s, d)
    return dest


def prepare(work: Path, only: set[str] | None, private: Path | None) -> list[dict[str, Any]]:
    """[{name, root, questions_path}] for every repo to evaluate."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    repos: list[dict[str, Any]] = []
    for repo in manifest["repos"]:
        if only and repo["name"] not in only:
            continue
        root = _pinned_clone(work, repo)
        repos.append(
            {
                "name": repo["name"],
                "root": root,
                "questions": QUESTIONS / f"{repo['name']}.eval.yaml",
            }
        )
    if not only or "neuralmind" in only:
        root = _copy_git_visible(REPO_ROOT, work / "neuralmind")
        # This repo's .neuralmindignore drops every markdown file. Spec 7 is
        # about docs competing with code for L3 slots, and six of its
        # questions are answered by a doc, so the eval indexes the docs.
        (root / ".neuralmindignore").unlink(missing_ok=True)
        repos.append(
            {"name": "neuralmind", "root": root, "questions": QUESTIONS / "neuralmind.eval.yaml"}
        )
    if private is not None:
        questions = private / ".neuralmind.eval.yaml"
        root = _copy_git_visible(private, work / "private")
        repos.append({"name": "private", "root": root, "questions": questions})
    return repos


# --------------------------------------------------------------------------- #
# Running
# --------------------------------------------------------------------------- #
def _set_flags(env: dict[str, str]) -> None:
    for name in FLAGS:
        os.environ.pop(name, None)
    os.environ.update(env)


def build(root: Path) -> float:
    from neuralmind.core import NeuralMind

    _set_flags({})
    start = time.perf_counter()
    result = NeuralMind(str(root)).build()
    if not result.get("success"):
        raise RuntimeError(f"build failed for {root}: {result.get('error')}")
    return time.perf_counter() - start


def eval_config(root: Path, questions_path: Path, env: dict[str, str]) -> dict[str, Any]:
    from neuralmind.core import NeuralMind
    from neuralmind.project_eval import load_questions, run_eval

    _set_flags(env)
    try:
        questions = load_questions(root, questions_path)
        mind = NeuralMind(str(root))  # fresh selector: no cache shared across configs
        report = run_eval(root, questions, mind=mind)
    finally:
        _set_flags({})
    return {
        "n": report.n_questions,
        "hit_at_1": report.hit_at_1,
        "hit_at_5": report.hit_at_5,
        "mrr": report.mrr,
        "avg_tokens": report.avg_context_tokens,
        "ranks": [r.rank for r in report.results],
    }


def public_benchmark(work: Path, env: dict[str, str]) -> float | None:
    """Query-weighted gold-file recall of the neuralmind backend under ``env``."""
    run_env = {k: v for k, v in os.environ.items() if k not in FLAGS}
    run_env.update(env)
    proc = subprocess.run(
        [sys.executable, "-m", "evals.public.run", "--json", "--work-dir", str(work)],
        cwd=REPO_ROOT,
        env=run_env,
        capture_output=True,
        text=True,
        timeout=3600,
    )
    if proc.returncode != 0:
        print(proc.stderr[-2000:], file=sys.stderr)
        return None
    report = json.loads(proc.stdout)
    n = recall = 0.0
    for repo in report.get("repos", []):
        s = (repo.get("summary") or {}).get("neuralmind")
        if s:
            n += s["n"]
            recall += s["n"] * s["mean_recall"]
    return round(recall / n, 4) if n else None


# --------------------------------------------------------------------------- #
# The keep rule
# --------------------------------------------------------------------------- #
def gate(results: dict[str, dict[str, dict]], config: str) -> dict[str, Any]:
    """Apply spec 7's keep rule to one configuration against ``baseline``."""
    deltas_q: dict[str, int] = {}
    deltas_h5: list[float] = []
    token_rise: list[float] = []
    for repo, by_config in results.items():
        base, cand = by_config["baseline"], by_config[config]
        hits_base = round(base["hit_at_5"] * base["n"])
        hits_cand = round(cand["hit_at_5"] * cand["n"])
        deltas_q[repo] = hits_cand - hits_base
        deltas_h5.append(cand["hit_at_5"] - base["hit_at_5"])
        if base["avg_tokens"]:
            token_rise.append(cand["avg_tokens"] / base["avg_tokens"] - 1)
    improved = sum(1 for d in deltas_q.values() if d > 0)
    worst = min(deltas_q.values()) if deltas_q else 0
    mean_delta = sum(deltas_h5) / len(deltas_h5) if deltas_h5 else 0.0
    mean_rise = sum(token_rise) / len(token_rise) if token_rise else 0.0
    checks = {
        "mean hit@5 rises": mean_delta > 0,
        f"improves ≥{MIN_REPOS_IMPROVED} repos": improved >= MIN_REPOS_IMPROVED,
        f"no repo drops >{MAX_DROP_QUESTIONS} question": worst >= -MAX_DROP_QUESTIONS,
        f"tokens ≤ +{MAX_TOKEN_RISE:.0%}": mean_rise <= MAX_TOKEN_RISE,
    }
    return {
        "config": config,
        "mean_hit_at_5_delta": round(mean_delta, 4),
        "repos_improved": improved,
        "worst_repo_delta_questions": worst,
        "per_repo_delta_questions": deltas_q,
        "mean_token_rise": round(mean_rise, 4),
        "checks": checks,
        "keep": all(checks.values()),
    }


def render(results: dict, gates: list[dict], public: dict[str, float | None]) -> str:
    configs = list(next(iter(results.values())).keys()) if results else []
    lines = ["# Retrieval eval — spec 7 work items", ""]
    lines.append("hit@5 / MRR / avg tokens per repo and configuration (30 questions each).")
    lines.append("")
    lines.append("| Repo | " + " | ".join(configs) + " |")
    lines.append("|---|" + "---:|" * len(configs))
    for repo, by_config in results.items():
        cells = []
        for c in configs:
            r = by_config[c]
            cells.append(f"{r['hit_at_5']:.0%} / {r['mrr']:.2f} / {r['avg_tokens']:,.0f}")
        lines.append(f"| {repo} | " + " | ".join(cells) + " |")
    means = []
    for c in configs:
        h5 = sum(results[r][c]["hit_at_5"] for r in results) / len(results)
        mrr = sum(results[r][c]["mrr"] for r in results) / len(results)
        means.append(f"**{h5:.1%} / {mrr:.3f}**")
    lines.append("| **mean** | " + " | ".join(means) + " |")
    lines.append("")
    lines.append("## Keep rule")
    lines.append("")
    lines.append(
        "| Config | Δ mean hit@5 | Repos improved | Worst repo (questions) | Δ tokens | "
        "Public recall | Keep |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|---|")
    base_pub = public.get("baseline")
    for g in gates:
        pub = public.get(g["config"])
        pub_s = f"{pub:.2%}" if pub is not None else "—"
        keep = g["keep"] and (pub is None or base_pub is None or pub >= base_pub)
        lines.append(
            f"| {g['config']} | {g['mean_hit_at_5_delta']:+.1%} | {g['repos_improved']} | "
            f"{g['worst_repo_delta_questions']:+d} | {g['mean_token_rise']:+.1%} | {pub_s} | "
            f"{'yes' if keep else 'no'} |"
        )
    if base_pub is not None:
        lines.append("")
        lines.append(f"Public benchmark baseline recall: {base_pub:.2%}.")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--work-dir", default=".bench-work", help="clones and copies go here")
    ap.add_argument("--repos", default="", help="comma-separated subset (default: all)")
    ap.add_argument("--private", default="", help="path to a private repo with its own eval")
    ap.add_argument("--configs", default=",".join(CONFIGS), help="comma-separated configs")
    ap.add_argument(
        "--public-benchmark", action="store_true", help="re-run evals.public per config"
    )
    ap.add_argument("--out", default="", help="write results.json + report.md here")
    ap.add_argument("--no-build", action="store_true", help="reuse existing indexes")
    args = ap.parse_args(argv)

    work = Path(args.work_dir).resolve()
    work.mkdir(parents=True, exist_ok=True)
    only = {r for r in args.repos.split(",") if r} or None
    private = Path(args.private).expanduser().resolve() if args.private else None
    configs = [c for c in args.configs.split(",") if c]
    if "baseline" not in configs:
        configs.insert(0, "baseline")

    repos = prepare(work, only, private)
    results: dict[str, dict[str, dict]] = {}
    for repo in repos:
        if not args.no_build:
            secs = build(repo["root"])
            print(f"[{repo['name']}] built in {secs:.0f}s", file=sys.stderr)
        results[repo["name"]] = {}
        for config in configs:
            r = eval_config(repo["root"], repo["questions"], CONFIGS[config])
            results[repo["name"]][config] = r
            print(
                f"[{repo['name']}] {config:<10} hit@5 {r['hit_at_5']:.0%}  "
                f"MRR {r['mrr']:.2f}  tokens {r['avg_tokens']:,.0f}",
                file=sys.stderr,
            )

    gates = [gate(results, c) for c in configs if c != "baseline"]
    public: dict[str, float | None] = {}
    if args.public_benchmark:
        for config in configs:
            public[config] = public_benchmark(work, CONFIGS[config])
            print(f"[public] {config:<10} recall {public[config]}", file=sys.stderr)

    report = render(results, gates, public)
    print(report)
    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        # Per-question ranks only for public repos; a private repo is aggregate-only.
        for repo, by_config in results.items():
            if repo == "private":
                for r in by_config.values():
                    r.pop("ranks", None)
        payload = {"configs": CONFIGS, "results": results, "gates": gates, "public": public}
        (out / "results.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        (out / "report.md").write_text(report, encoding="utf-8")
        print(f"wrote {out / 'results.json'} and {out / 'report.md'}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
