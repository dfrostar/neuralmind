"""Multi-repo retrieval eval: does a ranking change earn its place? (spec 7)

    python -m evals.retrieval.run                          # public repos + this one
    python -m evals.retrieval.run --private ~/work/app     # add a private repo (local only)
    python -m evals.retrieval.run --configs baseline,per_file --out bench/retrieval
    python -m evals.retrieval.run --public-benchmark       # also re-run evals.public per config
    python -m evals.retrieval.run --compare old/results.json new/results.json   # two releases

Every v4.6.0 ranking change sits behind a flag. This harness runs the
pre-registered questions in ``evals/retrieval/questions/`` (30 per repo,
written before any change was tried) once per flag configuration, read-only,
and applies a paired keep rule to every configuration against ``baseline``:

* pooled over every question, the configuration wins more hit@5 questions
  than it loses, and an exact McNemar test on those discordant questions
  gives p < 0.05;
* no repo drops by more than two questions (non-inferiority, per repo);
* average context tokens rise by at most 10%;
* the public 4-repo benchmark's gold-file recall doesn't drop
  (``--public-benchmark``).

The report also gives the mean MRR change with a paired bootstrap 95%
interval, and p50/p95 query latency per repo. (The rule this replaced asked
for a rise on three of the repos; with 30 questions a repo, one question is
3.3 points, and it rejected a change that raised two repos and lowered none.)

Repos: requests, click, flask and rich at the public benchmark's pinned
commits (cloned on demand), plus this repository. ``--private PATH`` adds a
repository whose questions live in its own ``.neuralmind.eval.yaml``; it is
copied to the work dir (so its own ``.neuralmind/`` is never touched) and
reported only in aggregate, as ``private``.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
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
    "NEURALMIND_L3_K",
    "NEURALMIND_L3_POOL",
    "NEURALMIND_CODE_SIGNAL_CAP",
    "NEURALMIND_AUTO_INTENT_BOOST",
    "NEURALMIND_QUERY_LAYERS",
    "NEURALMIND_L3_PER_FILE",
    "NEURALMIND_DOC_HANDOFF",
    "NEURALMIND_HUB_DAMPEN",
    "NEURALMIND_BM25_CODE",
    "NEURALMIND_BM25",
    "NEURALMIND_INTENT_RULES",
    "NEURALMIND_BM25_UNIFIED",
    "NEURALMIND_INTENT_POOL",
)

# One configuration per work item, the all-on combination, and the BM25-off
# comparison spec 7 item 5 asks for before building anything new.
CONFIGS: dict[str, dict[str, str]] = {
    "baseline": {},
    # v4.5.0's keyword index (turbovec: docs only), for the record after the
    # unified index became the default in v4.6.0.
    "v45_bm25": {"NEURALMIND_BM25_UNIFIED": "0"},
    "per_file": {"NEURALMIND_L3_PER_FILE": "2"},
    "handoff": {"NEURALMIND_DOC_HANDOFF": "1"},
    "hub": {"NEURALMIND_HUB_DAMPEN": "1"},
    "code_bm25": {"NEURALMIND_BM25_CODE": "1"},
    "bm25_off": {"NEURALMIND_BM25": "0"},
    "intent": {"NEURALMIND_INTENT_RULES": "1"},
    # Round 2, designed after round 1's results (see bench/retrieval/report.md):
    "bm25_unified": {"NEURALMIND_BM25_UNIFIED": "1"},
    "intent_pool": {"NEURALMIND_INTENT_RULES": "1", "NEURALMIND_INTENT_POOL": "1"},
    "unified_intent_pool": {
        "NEURALMIND_BM25_UNIFIED": "1",
        "NEURALMIND_INTENT_RULES": "1",
        "NEURALMIND_INTENT_POOL": "1",
    },
    # v4.12 retrieval, one item at a time against its new defaults: each
    # configuration puts one setting back the way it was.
    "l3_k4": {"NEURALMIND_L3_K": "4"},
    "code_signal": {"NEURALMIND_CODE_SIGNAL_CAP": "10"},
    "auto_intent": {"NEURALMIND_AUTO_INTENT_BOOST": "1"},
    "l3_only": {"NEURALMIND_QUERY_LAYERS": "L0,L3"},
    "all": {
        "NEURALMIND_L3_PER_FILE": "2",
        "NEURALMIND_DOC_HANDOFF": "1",
        "NEURALMIND_HUB_DAMPEN": "1",
        "NEURALMIND_BM25_CODE": "1",
        "NEURALMIND_INTENT_RULES": "1",
    },
}

MAX_P_VALUE = 0.05
MAX_DROP_QUESTIONS = 2
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


def prepare(
    work: Path, only: set[str] | None, private: Path | None, fresh: bool = True
) -> list[dict[str, Any]]:
    """[{name, root, questions_path}] for every repo to evaluate.

    With ``fresh`` (the default), each pinned clone's ``.neuralmind/`` is
    removed so the index is rebuilt from nothing: any learned state (synapses
    from a learning query) would otherwise change what the baseline returns.
    """
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    repos: list[dict[str, Any]] = []
    for repo in manifest["repos"]:
        if only and repo["name"] not in only:
            continue
        root = _pinned_clone(work, repo)
        if fresh:
            shutil.rmtree(root / ".neuralmind", ignore_errors=True)
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
        mind = _TimedMind(NeuralMind(str(root)))  # fresh selector per config
        report = run_eval(root, questions, mind=mind)
    finally:
        _set_flags({})
    return {
        "n": report.n_questions,
        "hit_at_1": report.hit_at_1,
        "hit_at_5": report.hit_at_5,
        "mrr": report.mrr,
        "avg_tokens": report.avg_context_tokens,
        "latency_ms_p50": _percentile(mind.latencies_ms, 50),
        "latency_ms_p95": _percentile(mind.latencies_ms, 95),
        "ranks": [r.rank for r in report.results],
    }


class _TimedMind:
    """A NeuralMind that records how long each ``query`` takes."""

    def __init__(self, mind: Any) -> None:
        self._mind = mind
        self.latencies_ms: list[float] = []

    def query(self, *args: Any, **kwargs: Any) -> Any:
        start = time.perf_counter()
        try:
            return self._mind.query(*args, **kwargs)
        finally:
            self.latencies_ms.append((time.perf_counter() - start) * 1000)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._mind, name)


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    k = min(len(ordered) - 1, max(0, round(pct / 100 * (len(ordered) - 1))))
    return round(ordered[k], 1)


def _fresh_public_workdir(work: Path, config: str) -> Path:
    """A clean copy of the pinned clones for one public-benchmark run.

    ``evals.public`` queries with learning on, so it trains the index it runs
    against. Each configuration gets its own copy (no ``.neuralmind/``), so no
    run sees the synapses an earlier one learned — and the eval's own
    indexes are never touched.
    """
    dest = work / "public-runs" / config
    shutil.rmtree(dest, ignore_errors=True)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for repo in manifest["repos"]:
        src = work / repo["name"]
        if not (src / ".git").exists():
            _pinned_clone(work, repo)
        shutil.copytree(src, dest / repo["name"], ignore=shutil.ignore_patterns(".neuralmind"))
    return dest


def public_benchmark(work: Path, config: str, env: dict[str, str]) -> float | None:
    """Query-weighted gold-file recall of the neuralmind backend under ``env``."""
    run_env = {k: v for k, v in os.environ.items() if k not in FLAGS}
    run_env.update(env)
    run_dir = _fresh_public_workdir(work, config)
    proc = subprocess.run(
        [sys.executable, "-m", "evals.public.run", "--json", "--work-dir", str(run_dir)],
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
def mcnemar_exact(wins: int, losses: int) -> float:
    """Two-sided exact McNemar p-value for ``wins`` vs ``losses`` discordant pairs."""
    n = wins + losses
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, k) for k in range(min(wins, losses) + 1)) / 2**n
    return min(1.0, 2 * tail)


def bootstrap_ci(diffs: list[float], reps: int = 2000, seed: int = 0) -> tuple[float, float]:
    """Paired bootstrap 95% interval for the mean of ``diffs`` (deterministic)."""
    if not diffs:
        return 0.0, 0.0
    rng = random.Random(seed)
    n = len(diffs)
    means = sorted(sum(rng.choice(diffs) for _ in range(n)) / n for _ in range(reps))
    return means[int(0.025 * reps)], means[int(0.975 * reps) - 1]


def _hit5(rank: int | None) -> int:
    return 1 if rank is not None and rank <= 5 else 0


def _rr(rank: int | None) -> float:
    return 1.0 / rank if rank else 0.0


def gate(results: dict[str, dict[str, dict]], config: str) -> dict[str, Any]:
    """Apply the paired keep rule to one configuration against ``baseline``."""
    deltas_q: dict[str, int] = {}
    token_rise: list[float] = []
    wins = losses = 0
    rr_diffs: list[float] = []
    for repo, by_config in results.items():
        base, cand = by_config["baseline"], by_config[config]
        repo_delta = 0
        for rb, rc in zip(base["ranks"], cand["ranks"], strict=True):
            d = _hit5(rc) - _hit5(rb)
            wins += d > 0
            losses += d < 0
            repo_delta += d
            rr_diffs.append(_rr(rc) - _rr(rb))
        deltas_q[repo] = repo_delta
        if base["avg_tokens"]:
            token_rise.append(cand["avg_tokens"] / base["avg_tokens"] - 1)
    worst = min(deltas_q.values()) if deltas_q else 0
    mean_rise = sum(token_rise) / len(token_rise) if token_rise else 0.0
    p_value = mcnemar_exact(wins, losses)
    lo, hi = bootstrap_ci(rr_diffs)
    checks = {
        f"wins > losses, McNemar p < {MAX_P_VALUE}": wins > losses and p_value < MAX_P_VALUE,
        f"no repo drops >{MAX_DROP_QUESTIONS} questions": worst >= -MAX_DROP_QUESTIONS,
        f"tokens ≤ +{MAX_TOKEN_RISE:.0%}": mean_rise <= MAX_TOKEN_RISE,
    }
    return {
        "config": config,
        "wins": wins,
        "losses": losses,
        "p_value": round(p_value, 4),
        "mean_mrr_delta": round(sum(rr_diffs) / len(rr_diffs), 4) if rr_diffs else 0.0,
        "mrr_delta_ci95": [round(lo, 4), round(hi, 4)],
        "worst_repo_delta_questions": worst,
        "per_repo_delta_questions": deltas_q,
        "mean_token_rise": round(mean_rise, 4),
        "checks": checks,
        "keep": all(checks.values()),
    }


def render(
    results: dict,
    gates: list[dict],
    public: dict[str, float | None],
    repeat: dict[str, bool] | None = None,
) -> str:
    configs = list(next(iter(results.values())).keys()) if results else []
    lines = ["# Retrieval eval", ""]
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
    lines.append("Query latency p50 / p95 (ms), baseline configuration:")
    lines.append("")
    for repo, by_config in results.items():
        b = by_config.get("baseline", {})
        lines.append(
            f"- {repo}: {b.get('latency_ms_p50', 0):,.0f} / {b.get('latency_ms_p95', 0):,.0f}"
        )
    lines.append("")
    lines.append("## Keep rule (paired, against baseline)")
    lines.append("")
    lines.append(
        "| Config | hit@5 won / lost | McNemar p | Δ MRR [95% CI] | Worst repo (questions) | "
        "Δ tokens | Public recall | Keep |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|---:|---|")
    base_pub = public.get("baseline")
    for g in gates:
        pub = public.get(g["config"])
        pub_s = f"{pub:.2%}" if pub is not None else "—"
        keep = g["keep"] and (pub is None or base_pub is None or pub >= base_pub)
        lo, hi = g["mrr_delta_ci95"]
        lines.append(
            f"| {g['config']} | {g['wins']} / {g['losses']} | {g['p_value']:.3f} | "
            f"{g['mean_mrr_delta']:+.3f} [{lo:+.3f}, {hi:+.3f}] | "
            f"{g['worst_repo_delta_questions']:+d} | {g['mean_token_rise']:+.1%} | {pub_s} | "
            f"{'yes' if keep else 'no'} |"
        )
    if base_pub is not None:
        lines.append("")
        lines.append(f"Public benchmark baseline recall: {base_pub:.2%}.")
    if repeat:
        same = [r for r, ok in repeat.items() if ok]
        differ = [r for r, ok in repeat.items() if not ok]
        lines.append("")
        if differ:
            lines.append(
                f"**Baseline did not reproduce** on {', '.join(differ)}: a second baseline run "
                "after every configuration returned different ranks. Treat deltas there as noise."
            )
        else:
            lines.append(
                f"Baseline reproduced exactly on all {len(same)} repos (re-run after every "
                "configuration): the deltas above are the flags, not state left behind."
            )
    return "\n".join(lines) + "\n"


def regressions(g: dict[str, Any]) -> list[str]:
    """Why a paired comparison counts as a regression; empty when it doesn't.

    The CI gate for retrieval-path changes. Unlike the keep rule it doesn't
    ask a change to *gain*, so a refactor that moves nothing passes: it fails
    on a significant loss (more hit@5 questions lost than won, exact McNemar
    p < 0.05), on any repo losing more than two questions, or on tokens rising
    more than 10%.
    """
    reasons = []
    if g["losses"] > g["wins"] and g["p_value"] < MAX_P_VALUE:
        reasons.append(
            f"hit@5: {g['losses']} questions lost, {g['wins']} won (McNemar p = {g['p_value']:.4f})"
        )
    for repo, delta in g["per_repo_delta_questions"].items():
        if delta < -MAX_DROP_QUESTIONS:
            reasons.append(f"{repo}: {-delta} questions lost (at most {MAX_DROP_QUESTIONS})")
    if g["mean_token_rise"] > MAX_TOKEN_RISE:
        reasons.append(f"tokens {g['mean_token_rise']:+.1%} (at most +{MAX_TOKEN_RISE:.0%})")
    return reasons


def compare(old_path: Path, new_path: Path) -> str:
    """The paired keep rule between two runs' ``baseline`` configurations.

    For comparing releases: run the eval once on each (``--out``), then
    ``--compare old/results.json new/results.json``. Repos in both are
    paired question by question.
    """
    return compare_with_gate(old_path, new_path)[0]


def compare_with_gate(old_path: Path, new_path: Path) -> tuple[str, dict[str, Any]]:
    """:func:`compare`'s report, and the gate it was computed from."""
    old = json.loads(Path(old_path).read_text(encoding="utf-8"))["results"]
    new = json.loads(Path(new_path).read_text(encoding="utf-8"))["results"]
    paired = {
        repo: {"baseline": old[repo]["baseline"], "new": new[repo]["baseline"]}
        for repo in old
        if repo in new
    }
    g = gate(paired, "new")

    def pooled(side: str, key: str) -> float:
        n = sum(paired[r][side]["n"] for r in paired)
        return sum(paired[r][side][key] * paired[r][side]["n"] for r in paired) / n

    lines = [
        f"# Retrieval eval — `{Path(old_path).name}` vs `{Path(new_path).name}`",
        "",
        "hit@5 / MRR / avg tokens, 30 questions per repo.",
        "",
        "| Repo | old | new |",
        "|---|---:|---:|",
    ]
    for repo, sides in paired.items():
        cells = [
            f"{sides[s]['hit_at_5']:.0%} / {sides[s]['mrr']:.2f} / {sides[s]['avg_tokens']:,.0f}"
            for s in ("baseline", "new")
        ]
        lines.append(f"| {repo} | " + " | ".join(cells) + " |")
    lines.append(
        f"| **pooled** | **{pooled('baseline', 'hit_at_5'):.1%} / "
        f"{pooled('baseline', 'mrr'):.3f} / {pooled('baseline', 'avg_tokens'):,.0f}** | "
        f"**{pooled('new', 'hit_at_5'):.1%} / {pooled('new', 'mrr'):.3f} / "
        f"{pooled('new', 'avg_tokens'):,.0f}** |"
    )
    lo, hi = g["mrr_delta_ci95"]
    lines += [
        "",
        f"hit@5 questions won / lost: **{g['wins']} / {g['losses']}** (exact McNemar "
        f"p = {g['p_value']:.4f}); per repo: "
        + ", ".join(f"{r} {d:+d}" for r, d in g["per_repo_delta_questions"].items())
        + f". Mean MRR change {g['mean_mrr_delta']:+.3f} (paired bootstrap 95% interval "
        f"[{lo:+.3f}, {hi:+.3f}]); mean tokens {g['mean_token_rise']:+.1%}.",
        "",
        "Keep rule: "
        + ("**passes**" if g["keep"] else "**fails**")
        + " — "
        + "; ".join(f"{k}: {'yes' if v else 'no'}" for k, v in g["checks"].items())
        + ".",
    ]
    found = regressions(g)
    lines += [
        "",
        "Regression check: "
        + ("**fails** — " + "; ".join(found) + "." if found else "**passes**."),
    ]
    return "\n".join(lines) + "\n", g


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
    ap.add_argument(
        "--compare",
        nargs=2,
        metavar=("OLD", "NEW"),
        help="pair two runs' results.json (e.g. two releases) instead of running",
    )
    ap.add_argument(
        "--fail-on-regression",
        action="store_true",
        help="with --compare: exit 1 if NEW regresses against OLD (the CI gate)",
    )
    args = ap.parse_args(argv)
    if args.compare:
        report, g = compare_with_gate(Path(args.compare[0]), Path(args.compare[1]))
        print(report, end="")
        if args.out:
            out = Path(args.out)
            out.mkdir(parents=True, exist_ok=True)
            (out / "report.md").write_text(report, encoding="utf-8")
        return 1 if args.fail_on_regression and regressions(g) else 0

    work = Path(args.work_dir).resolve()
    work.mkdir(parents=True, exist_ok=True)
    only = {r for r in args.repos.split(",") if r} or None
    private = Path(args.private).expanduser().resolve() if args.private else None
    configs = [c for c in args.configs.split(",") if c]
    if "baseline" not in configs:
        configs.insert(0, "baseline")

    repos = prepare(work, only, private, fresh=not args.no_build)
    results: dict[str, dict[str, dict]] = {}
    repeat: dict[str, bool] = {}
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
        # Determinism check: the baseline again, after every configuration ran.
        again = eval_config(repo["root"], repo["questions"], CONFIGS["baseline"])
        repeat[repo["name"]] = again["ranks"] == results[repo["name"]]["baseline"]["ranks"]
        print(f"[{repo['name']}] baseline reproduced: {repeat[repo['name']]}", file=sys.stderr)

    gates = [gate(results, c) for c in configs if c != "baseline"]
    public: dict[str, float | None] = {}
    if args.public_benchmark:
        for config in configs:
            public[config] = public_benchmark(work, config, CONFIGS[config])
            print(f"[public] {config:<10} recall {public[config]}", file=sys.stderr)

    report = render(results, gates, public, repeat)
    print(report)
    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        # Per-question ranks only for public repos; a private repo is aggregate-only.
        for repo, by_config in results.items():
            if repo == "private":
                for r in by_config.values():
                    r.pop("ranks", None)
        payload = {
            "configs": CONFIGS,
            "results": results,
            "gates": gates,
            "public": public,
            "baseline_reproduced": repeat,
        }
        (out / "results.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        (out / "report.md").write_text(report, encoding="utf-8")
        print(f"wrote {out / 'results.json'} and {out / 'report.md'}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
