"""project_eval.py — measure retrieval on *this* project, against gold answers.

``neuralmind eval .`` reads ``.neuralmind.eval.yaml`` at the project root — a
list of questions, each with the file(s) that answer it::

    - q: How are refunds issued when an order is cancelled?
      gold: [app/refunds.py]

For each question it runs a **read-only** query (``learn=False``: the eval
never trains the synapse layer it measures), ranks the files the answer drew
on by their best hit score (the same relevance sidecar ``query --relevance``
returns), and reports:

* hit@1 and hit@5 — a gold file is the top file / in the top five
* MRR — mean of 1 / rank of the first gold file (0 when missed)
* average context tokens
* two reductions: vs the tokens of the gold files (what a perfect retriever
  would load) and vs the tokens of all the code the index covers (the measured
  baseline, see :mod:`neuralmind.baseline`)

Each run appends one row to ``.neuralmind/eval_history.jsonl`` (date, git sha,
NeuralMind version, node count, metrics), so ``eval --report`` can print the
trend as a markdown table. The questions file is meant to be committed — a
shared team baseline — while the history stays in the untracked
``.neuralmind/`` because it is machine-specific. Reports print metrics and the
question count only, unless ``--show-questions`` is passed, so questions that
name internal code don't end up in pasted issues and posts.
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

EVAL_FILENAME = ".neuralmind.eval.yaml"
HISTORY_FILENAME = "eval_history.jsonl"
LAST_RUN_FILENAME = "eval_last.json"


@dataclass
class EvalQuestion:
    q: str
    gold: list[str]


@dataclass
class QuestionResult:
    q: str
    gold: list[str]
    rank: int | None  # 1-based rank of the first gold file; None = miss
    files: list[str]  # ranked files the answer drew on
    tokens: int
    gold_tokens: int


@dataclass
class EvalReport:
    project: str
    date: str
    git_sha: str
    version: str
    node_count: int
    n_questions: int
    hit_at_1: float
    hit_at_5: float
    mrr: float
    avg_context_tokens: float
    ratio_vs_gold: float
    ratio_vs_indexed: float
    baseline_tokens: int
    baseline_source: str
    results: list[QuestionResult] = field(default_factory=list)

    def history_row(self) -> dict[str, Any]:
        row = asdict(self)
        row.pop("results")
        return row

    def to_dict(self, show_questions: bool = False) -> dict[str, Any]:
        out = self.history_row()
        if show_questions:
            out["results"] = [asdict(r) for r in self.results]
        return out


# --------------------------------------------------------------------------- #
# Questions file
# --------------------------------------------------------------------------- #
def eval_file(project: str | Path) -> Path:
    return Path(project) / EVAL_FILENAME


def _normalize_rel(path: str) -> str:
    from .freshness import normalize_source_path

    return normalize_source_path(str(path), Path("/"))


def load_questions(project: str | Path, path: str | Path | None = None) -> list[EvalQuestion]:
    """Questions from ``.neuralmind.eval.yaml`` (or ``path``); [] when absent.

    Accepts a top-level list or ``{"questions": [...]}``. Each entry needs a
    non-empty ``q`` and ``gold`` (a path or list of paths); malformed entries
    raise ``ValueError`` naming the entry, so a typo isn't silently skipped.
    """
    source = Path(path) if path else eval_file(project)
    if not source.exists():
        return []
    import yaml

    data = yaml.safe_load(source.read_text(encoding="utf-8")) or []
    if isinstance(data, dict):
        data = data.get("questions", [])
    if not isinstance(data, list):
        raise ValueError(f"{source}: expected a list of {{q, gold}} entries")
    questions: list[EvalQuestion] = []
    for i, entry in enumerate(data, 1):
        if not isinstance(entry, dict):
            raise ValueError(f"{source}: entry {i} is not a mapping")
        q = str(entry.get("q") or entry.get("question") or "").strip()
        gold = entry.get("gold")
        if isinstance(gold, str):
            gold = [gold]
        if not q or not gold:
            raise ValueError(f"{source}: entry {i} needs both 'q' and 'gold'")
        questions.append(EvalQuestion(q=q, gold=[_normalize_rel(g) for g in gold]))
    return questions


# --------------------------------------------------------------------------- #
# Scoring
# --------------------------------------------------------------------------- #
def rank_files(top_search_hits: list[dict] | None, mind: Any = None) -> list[str]:
    """Files the answer drew on, best first (by each file's max hit score)."""
    from .relevance import build_relevance_sidecar

    sidecar = build_relevance_sidecar(top_search_hits, mind)
    files = sidecar.get("files", {}) or {}
    ranked = sorted(files.items(), key=lambda kv: -float(kv[1].get("max_score", 0.0) or 0.0))
    out: list[str] = []
    for name, _ in ranked:
        rel = _normalize_rel(name)
        if rel and rel not in out:
            out.append(rel)
    return out


def first_gold_rank(files: list[str], gold: list[str]) -> int | None:
    wanted = set(gold)
    for i, f in enumerate(files, 1):
        if f in wanted:
            return i
    return None


def _git_sha(project: Path) -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", str(project), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return proc.stdout.strip() if proc.returncode == 0 else ""


def run_eval(
    project: str | Path,
    questions: list[EvalQuestion] | None = None,
    mind: Any = None,
) -> EvalReport:
    """Run every question read-only against the built index and score it."""
    from . import __version__
    from . import baseline as baseline_mod

    root = Path(project).resolve()
    if questions is None:
        questions = load_questions(root)
    if not questions:
        raise ValueError(
            f"no questions: add them to {eval_file(root)} "
            "(draft some with `neuralmind eval --suggest`)"
        )
    if mind is None:
        from .core import NeuralMind

        mind = NeuralMind(str(root))

    base = baseline_mod.resolve(root)
    gold_cache: dict[str, int] = {}

    def gold_tokens(paths: list[str]) -> int:
        total = 0
        for rel in paths:
            if rel not in gold_cache:
                gold_cache[rel] = baseline_mod.count_file_tokens([root / rel])
            total += gold_cache[rel]
        return total

    results: list[QuestionResult] = []
    for question in questions:
        result = mind.query(question.q, learn=False)
        files = rank_files(result.top_search_hits, mind)
        results.append(
            QuestionResult(
                q=question.q,
                gold=question.gold,
                rank=first_gold_rank(files, question.gold),
                files=files[:10],
                tokens=int(result.budget.total),
                gold_tokens=gold_tokens(question.gold),
            )
        )

    n = len(results)
    avg_tokens = sum(r.tokens for r in results) / n
    gold_ratios = [r.gold_tokens / r.tokens for r in results if r.tokens > 0 and r.gold_tokens]
    node_count = len(getattr(mind.embedder, "nodes", None) or [])
    return EvalReport(
        project=root.name,
        date=datetime.now().isoformat(timespec="seconds"),
        git_sha=_git_sha(root),
        version=__version__,
        node_count=node_count,
        n_questions=n,
        hit_at_1=round(sum(1 for r in results if r.rank == 1) / n, 4),
        hit_at_5=round(sum(1 for r in results if r.rank is not None and r.rank <= 5) / n, 4),
        mrr=round(sum(1.0 / r.rank for r in results if r.rank) / n, 4),
        avg_context_tokens=round(avg_tokens, 1),
        ratio_vs_gold=round(sum(gold_ratios) / len(gold_ratios), 2) if gold_ratios else 0.0,
        ratio_vs_indexed=round(base["tokens"] / avg_tokens, 1) if avg_tokens else 0.0,
        baseline_tokens=int(base["tokens"]),
        baseline_source=str(base["source"]),
        results=results,
    )


# --------------------------------------------------------------------------- #
# History and reports
# --------------------------------------------------------------------------- #
def history_path(project: str | Path) -> Path:
    return Path(project) / ".neuralmind" / HISTORY_FILENAME


def append_history(project: str | Path, report: EvalReport) -> Path:
    path = history_path(project)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(report.history_row()) + "\n")
    last = path.parent / LAST_RUN_FILENAME
    last.write_text(json.dumps(report.to_dict(show_questions=True), indent=2), encoding="utf-8")
    return path


def read_history(project: str | Path) -> list[dict[str, Any]]:
    path = history_path(project)
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue
    return rows


def _pct(value: float) -> str:
    return f"{value * 100:.0f}%"


def render_summary(report: EvalReport, show_questions: bool = False) -> str:
    lines = [
        f"NeuralMind eval — {report.project} ({report.n_questions} questions, read-only)",
        f"  hit@1 {_pct(report.hit_at_1)} · hit@5 {_pct(report.hit_at_5)} · MRR {report.mrr:.2f}",
        (
            f"  avg context {report.avg_context_tokens:,.0f} tokens · "
            f"{report.ratio_vs_gold:.1f}× vs gold files · "
            f"{report.ratio_vs_indexed:,.1f}× vs all indexed code "
            f"({report.baseline_tokens:,} tokens, {report.baseline_source})"
        ),
    ]
    if show_questions:
        lines.append("")
        lines.append("| # | Question | Gold | Rank | Top files |")
        lines.append("|---|----------|------|-----:|-----------|")
        for i, r in enumerate(report.results, 1):
            rank = str(r.rank) if r.rank else "miss"
            lines.append(
                f"| {i} | {r.q} | {', '.join(r.gold)} | {rank} | {', '.join(r.files[:4])} |"
            )
    return "\n".join(lines)


def render_report(rows: list[dict[str, Any]], last_run: dict[str, Any] | None = None) -> str:
    """Markdown table of the eval history — the format people paste into issues."""
    if not rows:
        return "No eval runs recorded yet. Run `neuralmind eval .` first."
    out = [
        (
            "| Date | Commit | NeuralMind | Nodes | Questions | hit@1 | hit@5 | MRR "
            "| Avg tokens | × vs gold | × vs indexed |"
        ),
        (
            "|------|--------|-----------|------:|----------:|------:|------:|----:"
            "|-----------:|----------:|-------------:|"
        ),
    ]
    for row in rows:
        out.append(
            f"| {str(row.get('date', ''))[:10]} | {row.get('git_sha') or '—'} "
            f"| {row.get('version', '')} | {int(row.get('node_count', 0)):,} "
            f"| {row.get('n_questions', 0)} | {_pct(float(row.get('hit_at_1', 0)))} "
            f"| {_pct(float(row.get('hit_at_5', 0)))} | {float(row.get('mrr', 0)):.2f} "
            f"| {float(row.get('avg_context_tokens', 0)):,.0f} "
            f"| {float(row.get('ratio_vs_gold', 0)):.1f}× "
            f"| {float(row.get('ratio_vs_indexed', 0)):,.1f}× |"
        )
    if last_run and last_run.get("results"):
        out.append("")
        out.append("Last run, per question:")
        out.append("")
        out.append("| # | Question | Gold | Rank | Top files |")
        out.append("|---|----------|------|-----:|-----------|")
        for i, r in enumerate(last_run["results"], 1):
            rank = str(r.get("rank")) if r.get("rank") else "miss"
            out.append(
                f"| {i} | {r.get('q', '')} | {', '.join(r.get('gold', []))} | {rank} "
                f"| {', '.join((r.get('files') or [])[:4])} |"
            )
    return "\n".join(out)


def read_last_run(project: str | Path) -> dict[str, Any] | None:
    path = Path(project) / ".neuralmind" / LAST_RUN_FILENAME
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


# --------------------------------------------------------------------------- #
# Drafting questions
# --------------------------------------------------------------------------- #
_HEADING_RE = re.compile(r"^#{2,3}\s+(.+?)\s*#*\s*$")
_WORD_RE = re.compile(r"[a-z0-9]+")
_STOP = frozenset(
    "a an the and or of to in for on with by from how what why does do is are this that "
    "it its as at be can into via using use used".split()
)


def _first_sentence(text: str) -> str:
    text = " ".join(text.strip().split())
    m = re.match(r"(.+?[.!?])(\s|$)", text)
    sentence = (m.group(1) if m else text).rstrip(".!?")
    return sentence[:120]


def _module_docstring(path: Path) -> str:
    try:
        src = path.read_text(encoding="utf-8")
    except OSError:
        return ""
    if path.suffix == ".py":
        try:
            return ast.get_docstring(ast.parse(src)) or ""
        except (SyntaxError, ValueError):
            return ""
    # Leading block comment for C-family / TS / Go / Rust files.
    m = re.match(r"\s*/\*\*?(.*?)\*/", src, re.S)
    if m:
        return re.sub(r"^\s*\*\s?", "", m.group(1), flags=re.M)
    lines = []
    for line in src.splitlines():
        stripped = line.strip()
        if stripped.startswith(("//", "#")) and not stripped.startswith("#!"):
            lines.append(stripped.lstrip("/#! ").strip())
        elif stripped:
            break
    return " ".join(lines)


def _words(text: str) -> set[str]:
    return {w for w in _WORD_RE.findall(text.lower()) if w not in _STOP and len(w) > 2}


def suggest_questions(project: str | Path, n: int = 10) -> list[dict[str, Any]]:
    """Draft ``n`` questions with the defining file as gold, for a human to edit.

    Sources: module docstrings (the module is the gold file) and README
    ``##``/``###`` headings (gold = the code file whose name and docstring
    share the most words with the heading; headings with no match are
    skipped). Drafts only — the person editing them knows the right answer.
    """
    from . import graphgen

    root = Path(project).resolve()
    code_files = graphgen._iter_files(root, graphgen._DEFAULT_IGNORES, graphgen._CODE_SUFFIXES)
    docs: list[tuple[str, str]] = []
    for path in code_files:
        if path.name.startswith("test_") or "/tests/" in f"/{path.relative_to(root).as_posix()}":
            continue
        doc = _module_docstring(path)
        if doc.strip():
            docs.append((path.relative_to(root).as_posix(), doc))

    drafts: list[dict[str, Any]] = []
    seen: set[str] = set()

    readme = next(
        (root / name for name in ("README.md", "readme.md") if (root / name).exists()), None
    )
    if readme is not None:
        index = [
            (rel, _words(rel.replace("/", " ").replace("_", " ") + " " + doc)) for rel, doc in docs
        ]
        for line in readme.read_text(encoding="utf-8", errors="replace").splitlines():
            m = _HEADING_RE.match(line)
            if not m:
                continue
            heading = re.sub(r"[`*_\[\]()]", "", m.group(1)).strip()
            words = _words(heading)
            if not words:
                continue
            best = max(index, key=lambda item: len(words & item[1]), default=None)
            if best is None or not (words & best[1]) or best[0] in seen:
                continue
            seen.add(best[0])
            drafts.append({"q": f"How does {heading.lower()} work?", "gold": [best[0]]})
            if len(drafts) >= n // 2:
                break

    for rel, doc in docs:
        if len(drafts) >= n:
            break
        if rel in seen:
            continue
        topic = _first_sentence(doc)
        if len(topic.split()) < 3:
            continue
        seen.add(rel)
        topic = topic[0].lower() + topic[1:]
        drafts.append({"q": f"Where is the code that does this: {topic}?", "gold": [rel]})
    return drafts[:n]


def render_suggestions(drafts: list[dict[str, Any]]) -> str:
    """YAML for ``.neuralmind.eval.yaml``, with an editing note on top."""
    import yaml

    header = (
        "# Draft eval questions from `neuralmind eval --suggest`. Edit before use:\n"
        "# rewrite each question the way a teammate would ask it, and fix any gold\n"
        "# file that isn't the one that answers it. Commit this file so the team\n"
        "# shares one baseline; run `neuralmind eval .` to score it.\n"
    )
    body = yaml.safe_dump(drafts, sort_keys=False, allow_unicode=True, width=100)
    return header + body
