"""Backend parity gate — graphify vs the built-in tree-sitter backend.

This is the safety net the graph-backend decoupling rests on. Every change to a
graph *producer* (the built-in tree-sitter backend, future TS/Go extractors, an
optional LSP/SCIP precision pass) has to clear it before it can ship.

What it does, per backend:

1. Build the reference fixture's index with that backend.
   * **graphify**  — ``graphify update`` writes ``graphify-out/graph.json``;
     ``neuralmind build --force`` consumes it (``--force`` never clobbers a
     real graphify graph).
   * **built-in**  — no graphify output present, so ``neuralmind build``
     auto-generates a graphify-compatible ``graph.json`` from a tree-sitter
     parse (``neuralmind/graphgen.py``).
2. Run the **faithfulness eval** (``evals/faithfulness``) against that index —
   the expected-fact-recall A/B vs a matched-budget naive baseline.
3. Derive the **self-benchmark reduction ratio** from the same selected
   contexts (whole-repo tokens ÷ NeuralMind's per-query budget), mirroring
   ``tests/benchmark/run.py`` Phase 1.

Then it **gates**: the built-in backend's reduction and faithfulness must stay
within tolerance of graphify's, and clear the same absolute floors the
standalone CI gates use. A regression here means a backend swap quietly made
retrieval worse — exactly what we never want to discover after a release.

Each backend builds into its own throwaway copy of the fixture, so the two
runs never share an index or a ``graphify-out/``.

Run locally::

    pip install ".[dev]" tiktoken graphifyy
    python -m evals.parity.run

Outputs ``evals/parity/parity_report.{md,json}`` and exits non-zero if the
built-in backend falls outside tolerance.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FIXTURE = _REPO_ROOT / "tests" / "fixtures" / "sample_project"

_REPORT_MD = Path(__file__).resolve().parent / "parity_report.md"
_REPORT_JSON = Path(__file__).resolve().parent / "parity_report.json"

# --------------------------------------------------------------------------- #
# Tolerances — overridable from the environment so the gate can be tightened
# as the measured distribution stabilises without touching code.
# --------------------------------------------------------------------------- #
# The built-in backend's mean reduction may sit at most this fraction below
# graphify's (0.25 = "within 25%").
REDUCTION_TOLERANCE = float(os.environ.get("NEURALMIND_PARITY_REDUCTION_TOL", "0.25"))
# The built-in backend's faithfulness delta / recall may sit at most this many
# points (absolute, 0.10 = 10 points) below graphify's.
FAITHFULNESS_TOLERANCE = float(os.environ.get("NEURALMIND_PARITY_FAITHFULNESS_TOL", "0.10"))
# Absolute floors, mirroring the standalone CI gates (ci-benchmark.yml):
# reduction must clear the benchmark's conservative floor, and the faithfulness
# delta must be non-negative (smart selection ≥ dumb truncation at equal cost).
REDUCTION_FLOOR = float(os.environ.get("NEURALMIND_PARITY_REDUCTION_FLOOR", "4.0"))
FAITHFULNESS_FLOOR = float(os.environ.get("NEURALMIND_PARITY_FAITHFULNESS_FLOOR", "0.0"))

# Multi-language structural parity. The faithfulness A/B needs a per-language
# gold-fact set (we have one only for the Python fixture), so for TypeScript and
# Go the gate proves parity *structurally*: the built-in backend must recover at
# least this fraction of the symbols graphify's committed graph found, with a
# valid, dangling-free graph. Fixtures: tests/fixtures/sample_project_{ts,go}.
SYMBOL_COVERAGE_FLOOR = float(os.environ.get("NEURALMIND_PARITY_COVERAGE_FLOOR", "0.90"))
_LANG_FIXTURES: dict[str, str] = {
    "typescript": "tests/fixtures/sample_project_ts",
    "go": "tests/fixtures/sample_project_go",
    "rust": "tests/fixtures/sample_project_rust",
    "java": "tests/fixtures/sample_project_java",
    "c": "tests/fixtures/sample_project_c",
    "cpp": "tests/fixtures/sample_project_cpp",
}


@dataclass
class BackendMeasurement:
    """One backend's measured retrieval quality on the reference fixture."""

    backend: str
    generated_by: str
    code_nodes: int
    mean_reduction: float
    faithfulness_delta: float
    nm_mean_recall: float
    naive_mean_recall: float
    nm_mean_grounding: float
    n_queries: int

    def to_dict(self) -> dict:
        return asdict(self)


# --------------------------------------------------------------------------- #
# Building each backend's index
# --------------------------------------------------------------------------- #
def _run(cmd: list[str], cwd: Path | None = None) -> None:
    """Run a subprocess, surfacing its output on failure."""
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"command failed ({proc.returncode}): {' '.join(cmd)}\n"
            f"--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}"
        )


def _copy_fixture(dst: Path) -> None:
    """Copy the reference fixture, dropping any pre-existing build artifacts."""
    shutil.copytree(
        _FIXTURE,
        dst,
        ignore=shutil.ignore_patterns(".neuralmind", "graphify-out", "__pycache__", "*.pyc"),
    )


def _graph_meta(project: Path) -> tuple[str, int]:
    """Return ``(generated_by, code_node_count)`` for a built graph."""
    graph_path = project / "graphify-out" / "graph.json"
    data = json.loads(graph_path.read_text(encoding="utf-8"))
    generated_by = str(data.get("generated_by", "graphify"))
    code_nodes = sum(1 for n in data.get("nodes", []) if n.get("file_type") == "code")
    return generated_by, code_nodes


def build_graphify(project: Path) -> tuple[str, int]:
    """Build the index from a real graphify graph."""
    _copy_fixture(project)
    _run(["graphify", "update", str(project)])
    _run(["neuralmind", "build", str(project), "--force"])
    generated_by, code_nodes = _graph_meta(project)
    if "neuralmind.graphgen" in generated_by:
        raise RuntimeError(
            "graphify backend produced a built-in graph — graphify is not "
            f"installed or did not run (generated_by={generated_by!r})"
        )
    return generated_by, code_nodes


def build_builtin(project: Path) -> tuple[str, int]:
    """Build the index from the built-in tree-sitter backend (no graphify)."""
    _copy_fixture(project)
    _run(["neuralmind", "build", str(project)])
    generated_by, code_nodes = _graph_meta(project)
    if "neuralmind.graphgen" not in generated_by:
        raise RuntimeError(
            "built-in backend did not generate the graph — a graphify graph "
            f"leaked into the copy (generated_by={generated_by!r})"
        )
    return generated_by, code_nodes


# --------------------------------------------------------------------------- #
# Measuring retrieval quality
# --------------------------------------------------------------------------- #
def measure(backend: str, project: Path, generated_by: str, code_nodes: int) -> BackendMeasurement:
    """Run the faithfulness eval + derive the reduction ratio for one backend."""
    from evals.faithfulness import harness

    report = harness.run_and_report(str(project))

    # Reduction = whole-repo tokens ÷ NeuralMind's per-query budget, averaged —
    # the same metric as tests/benchmark/run.py Phase 1, reusing the per-query
    # nm_tokens the faithfulness A/B already measured.
    whole_repo = harness.count_tokens(harness._fixture_source_text(project))
    ratios = [whole_repo / r.nm_tokens for r in report.per_query if r.nm_tokens > 0]
    mean_reduction = sum(ratios) / len(ratios) if ratios else 0.0

    return BackendMeasurement(
        backend=backend,
        generated_by=generated_by,
        code_nodes=code_nodes,
        mean_reduction=mean_reduction,
        faithfulness_delta=report.faithfulness_delta,
        nm_mean_recall=report.nm_mean_recall,
        naive_mean_recall=report.naive_mean_recall,
        nm_mean_grounding=report.nm_mean_grounding,
        n_queries=report.n_queries,
    )


# --------------------------------------------------------------------------- #
# Gate
# --------------------------------------------------------------------------- #
@dataclass
class GateCheck:
    name: str
    passed: bool
    detail: str


def evaluate_gate(graphify: BackendMeasurement, builtin: BackendMeasurement) -> list[GateCheck]:
    """The parity rules: built-in within tolerance of graphify + absolute floors."""
    checks: list[GateCheck] = []

    # 1. Reduction within tolerance of graphify.
    red_min = graphify.mean_reduction * (1.0 - REDUCTION_TOLERANCE)
    checks.append(
        GateCheck(
            "reduction within tolerance of graphify",
            builtin.mean_reduction >= red_min,
            f"built-in {builtin.mean_reduction:.2f}× ≥ "
            f"{red_min:.2f}× (graphify {graphify.mean_reduction:.2f}× "
            f"− {REDUCTION_TOLERANCE:.0%})",
        )
    )
    # 2. Reduction clears the absolute floor.
    checks.append(
        GateCheck(
            "reduction ≥ absolute floor",
            builtin.mean_reduction >= REDUCTION_FLOOR,
            f"built-in {builtin.mean_reduction:.2f}× ≥ floor {REDUCTION_FLOOR:.2f}×",
        )
    )
    # 3. Faithfulness delta within tolerance of graphify.
    faith_min = graphify.faithfulness_delta - FAITHFULNESS_TOLERANCE
    checks.append(
        GateCheck(
            "faithfulness delta within tolerance of graphify",
            builtin.faithfulness_delta >= faith_min,
            f"built-in {builtin.faithfulness_delta:+.3f} ≥ "
            f"{faith_min:+.3f} (graphify {graphify.faithfulness_delta:+.3f} "
            f"− {FAITHFULNESS_TOLERANCE:.2f})",
        )
    )
    # 4. Faithfulness delta clears the absolute floor.
    checks.append(
        GateCheck(
            "faithfulness delta ≥ absolute floor",
            builtin.faithfulness_delta >= FAITHFULNESS_FLOOR,
            f"built-in {builtin.faithfulness_delta:+.3f} ≥ floor {FAITHFULNESS_FLOOR:+.3f}",
        )
    )
    # 5. Fact recall within tolerance of graphify.
    recall_min = graphify.nm_mean_recall - FAITHFULNESS_TOLERANCE
    checks.append(
        GateCheck(
            "fact recall within tolerance of graphify",
            builtin.nm_mean_recall >= recall_min,
            f"built-in {builtin.nm_mean_recall:.3f} ≥ "
            f"{recall_min:.3f} (graphify {graphify.nm_mean_recall:.3f} "
            f"− {FAITHFULNESS_TOLERANCE:.2f})",
        )
    )
    return checks


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
def render_markdown(
    graphify: BackendMeasurement,
    builtin: BackendMeasurement,
    checks: list[GateCheck],
) -> str:
    passed = all(c.passed for c in checks)
    status = "✅ PASS" if passed else "❌ FAIL"
    lines = [
        "## Backend parity gate — graphify vs built-in tree-sitter",
        "",
        f"**{status}** — the built-in backend must stay within tolerance of "
        "graphify on the reference fixture.",
        "",
        "| Metric | graphify | built-in |",
        "|--------|---------:|---------:|",
        f"| code nodes | {graphify.code_nodes} | {builtin.code_nodes} |",
        f"| mean reduction | {graphify.mean_reduction:.2f}× | {builtin.mean_reduction:.2f}× |",
        f"| faithfulness delta | {graphify.faithfulness_delta:+.3f} | {builtin.faithfulness_delta:+.3f} |",
        f"| fact recall | {graphify.nm_mean_recall:.3f} | {builtin.nm_mean_recall:.3f} |",
        f"| grounding | {graphify.nm_mean_grounding:.3f} | {builtin.nm_mean_grounding:.3f} |",
        "",
        "### Gate checks",
        "",
    ]
    for c in checks:
        mark = "✅" if c.passed else "❌"
        lines.append(f"- {mark} **{c.name}** — {c.detail}")
    lines += [
        "",
        f"Tolerances: reduction within {REDUCTION_TOLERANCE:.0%} "
        f"(floor {REDUCTION_FLOOR:.1f}×), faithfulness within "
        f"{FAITHFULNESS_TOLERANCE:.2f} (floor {FAITHFULNESS_FLOOR:+.2f}). "
        "Override via `NEURALMIND_PARITY_*` env vars.",
        "",
        "_Automated by `evals/parity/run.py` — reproduce locally with "
        "`python -m evals.parity.run`._",
        "",
    ]
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Multi-language structural parity (TypeScript / Go)
# --------------------------------------------------------------------------- #
@dataclass
class LanguageCoverage:
    """How well the built-in backend recovers graphify's symbols for a language."""

    language: str
    graphify_symbols: int
    builtin_symbols: int
    covered: int
    dangling: int

    @property
    def coverage(self) -> float:
        return self.covered / self.graphify_symbols if self.graphify_symbols else 0.0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["coverage"] = round(self.coverage, 4)
        return d


def _code_symbols(graph: dict) -> set[str]:
    """Symbol set of a graph's ``code`` node labels (``()`` suffix normalised)."""
    return {
        str(n.get("label", "")).rstrip("()")
        for n in graph.get("nodes", [])
        if n.get("file_type") == "code" and n.get("label")
    }


def measure_language_coverage(language: str, fixture: str) -> LanguageCoverage:
    """Build the fixture with the built-in backend and compare its symbol set to
    graphify's committed ``graph.json``. Pure graph comparison — no chromadb."""
    from neuralmind import graphgen

    fixture_path = _REPO_ROOT / fixture
    graphify_graph = json.loads(
        (fixture_path / "graphify-out" / "graph.json").read_text(encoding="utf-8")
    )
    builtin_graph = graphgen.build_graph(fixture_path)

    gf_syms = _code_symbols(graphify_graph)
    bi_syms = _code_symbols(builtin_graph)
    ids = {n["id"] for n in builtin_graph.get("nodes", [])}
    dangling = sum(
        1
        for e in builtin_graph.get("links", [])
        if e["source"] not in ids or e["target"] not in ids
    )
    return LanguageCoverage(
        language=language,
        graphify_symbols=len(gf_syms),
        builtin_symbols=len(bi_syms),
        covered=len(gf_syms & bi_syms),
        dangling=dangling,
    )


def evaluate_language_gate(cov: LanguageCoverage) -> list[GateCheck]:
    return [
        GateCheck(
            f"{cov.language}: symbol coverage ≥ floor",
            cov.coverage >= SYMBOL_COVERAGE_FLOOR,
            f"{cov.covered}/{cov.graphify_symbols} graphify symbols "
            f"({cov.coverage:.0%}) ≥ {SYMBOL_COVERAGE_FLOOR:.0%}",
        ),
        GateCheck(
            f"{cov.language}: no dangling edges",
            cov.dangling == 0,
            f"{cov.dangling} dangling edge(s)",
        ),
    ]


def render_language_markdown(coverages: list[LanguageCoverage], checks: list[GateCheck]) -> str:
    lines = [
        "",
        "### Multi-language structural parity",
        "",
        "| Language | graphify symbols | built-in covers | dangling |",
        "|----------|-----------------:|----------------:|---------:|",
    ]
    for c in coverages:
        lines.append(
            f"| {c.language} | {c.graphify_symbols} | "
            f"{c.covered} ({c.coverage:.0%}) | {c.dangling} |"
        )
    lines.append("")
    for c in checks:
        mark = "✅" if c.passed else "❌"
        lines.append(f"- {mark} **{c.name}** — {c.detail}")
    lines += [
        "",
        f"Coverage floor: {SYMBOL_COVERAGE_FLOOR:.0%} of graphify's per-language "
        "symbols (no gold-fact set exists for TS/Go, so parity is structural).",
        "",
    ]
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Optional SCIP precision pass (Item 2)
# --------------------------------------------------------------------------- #
_PRECISION_FIXTURE = "tests/fixtures/scip_precision"
# The fixture has two classes with a `handle()` method; the bare-name heuristic
# links run() to the first (B.handle), which is wrong. SCIP resolves it to
# A.handle. Node ids are graphgen-deterministic.
_PRECISION_WRONG = ("app_py__run_fn", "app_py__b_cls__handle_fn")
_PRECISION_RIGHT = ("app_py__run_fn", "app_py__a_cls__handle_fn")


@dataclass
class PrecisionCheck:
    heuristic_has_wrong: bool
    precise_has_right: bool
    precise_drops_wrong: bool
    noop_when_disabled: bool

    def to_dict(self) -> dict:
        return asdict(self)


def measure_precision() -> PrecisionCheck:
    """Prove the SCIP precision pass corrects a call the heuristic gets wrong,
    and is a strict no-op when disabled."""
    import os

    from neuralmind import graphgen, precision

    fixture = _REPO_ROOT / _PRECISION_FIXTURE

    def call_edges(graph) -> set[tuple[str, str]]:
        return {(e["source"], e["target"]) for e in graph["links"] if e["relation"] == "calls"}

    heuristic = call_edges(graphgen.build_graph(fixture))
    index = precision.parse_scip_index((fixture / "index.scip").read_bytes())
    refined, _ = precision.refine_graph(graphgen.build_graph(fixture), index)
    precise = call_edges(refined)

    os.environ.pop("NEURALMIND_PRECISION", None)
    _, stats = precision.maybe_refine(fixture, graphgen.build_graph(fixture))

    return PrecisionCheck(
        heuristic_has_wrong=_PRECISION_WRONG in heuristic,
        precise_has_right=_PRECISION_RIGHT in precise,
        precise_drops_wrong=_PRECISION_WRONG not in precise,
        noop_when_disabled=stats is None,
    )


def evaluate_precision_gate(p: PrecisionCheck) -> list[GateCheck]:
    return [
        GateCheck(
            "precision: SCIP corrects the heuristic call edge",
            p.heuristic_has_wrong and p.precise_has_right and p.precise_drops_wrong,
            "run() → A.handle under SCIP (heuristic wrongly linked B.handle)",
        ),
        GateCheck(
            "precision: strict no-op when disabled",
            p.noop_when_disabled,
            "graph unchanged when NEURALMIND_PRECISION is unset",
        ),
    ]


def render_precision_markdown(checks: list[GateCheck]) -> str:
    lines = ["", "### Optional SCIP precision pass", ""]
    for c in checks:
        mark = "✅" if c.passed else "❌"
        lines.append(f"- {mark} **{c.name}** — {c.detail}")
    lines += [
        "",
        "Off by default (`NEURALMIND_PRECISION`); proven on "
        "`tests/fixtures/scip_precision` to replace a heuristic call edge with "
        "the compiler-accurate one a SCIP index resolves.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv

    measurements: dict[str, BackendMeasurement] = {}
    with tempfile.TemporaryDirectory(prefix="nm-parity-") as tmp:
        tmproot = Path(tmp)
        for backend, builder in (("graphify", build_graphify), ("builtin", build_builtin)):
            project = tmproot / backend
            print(f"[parity] building {backend} backend at {project} …", flush=True)
            generated_by, code_nodes = builder(project)
            print(f"[parity] {backend}: generated_by={generated_by!r} code_nodes={code_nodes}")
            measurements[backend] = measure(backend, project, generated_by, code_nodes)

    graphify = measurements["graphify"]
    builtin = measurements["builtin"]
    checks = evaluate_gate(graphify, builtin)

    # Multi-language structural parity (TypeScript, Go).
    lang_coverages: list[LanguageCoverage] = []
    lang_checks: list[GateCheck] = []
    for language, fixture in _LANG_FIXTURES.items():
        print(f"[parity] measuring {language} structural coverage ({fixture}) …", flush=True)
        cov = measure_language_coverage(language, fixture)
        print(
            f"[parity] {language}: {cov.covered}/{cov.graphify_symbols} symbols "
            f"({cov.coverage:.0%}), dangling={cov.dangling}"
        )
        lang_coverages.append(cov)
        lang_checks.extend(evaluate_language_gate(cov))

    # Optional SCIP precision pass (Item 2).
    print("[parity] checking SCIP precision pass …", flush=True)
    precision_result = measure_precision()
    precision_checks = evaluate_precision_gate(precision_result)
    print(
        f"[parity] precision: corrected={precision_result.precise_has_right and precision_result.precise_drops_wrong}, "
        f"noop_when_disabled={precision_result.noop_when_disabled}"
    )

    all_checks = checks + lang_checks + precision_checks
    passed = all(c.passed for c in all_checks)

    md = (
        render_markdown(graphify, builtin, checks)
        + render_language_markdown(lang_coverages, lang_checks)
        + render_precision_markdown(precision_checks)
    )
    _REPORT_MD.write_text(md, encoding="utf-8")
    _REPORT_JSON.write_text(
        json.dumps(
            {
                "passed": passed,
                "tolerances": {
                    "reduction": REDUCTION_TOLERANCE,
                    "faithfulness": FAITHFULNESS_TOLERANCE,
                    "reduction_floor": REDUCTION_FLOOR,
                    "faithfulness_floor": FAITHFULNESS_FLOOR,
                    "symbol_coverage": SYMBOL_COVERAGE_FLOOR,
                },
                "graphify": graphify.to_dict(),
                "builtin": builtin.to_dict(),
                "checks": [asdict(c) for c in checks],
                "language_coverage": [c.to_dict() for c in lang_coverages],
                "language_checks": [asdict(c) for c in lang_checks],
                "precision": precision_result.to_dict(),
                "precision_checks": [asdict(c) for c in precision_checks],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print("\n" + md)
    if not passed:
        print("\n[parity] GATE FAILED — built-in backend outside tolerance.", file=sys.stderr)
        return 1
    print("\n[parity] gate passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
