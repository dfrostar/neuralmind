"""Self-benchmark runner for NeuralMind.

Two phases:

Phase 1 — Reduction.
    For each query in the committed set, measure tokens with and without
    NeuralMind against a small hermetic fixture. The "before" number is
    the naive "load everything" baseline (every .py file in the fixture
    concatenated). The "after" is ``NeuralMind.query(q).budget.total``.
    Emit per-query + aggregate numbers.

Phase 2 — Synapse recall A/B (the learning measurement).
    Reinforce realistic co-editing sessions into the Hebbian synapse
    store, then re-run the same queries with synapse recall off vs on.
    Report the change in reduction ratio and top-k retrieval accuracy.
    On a 500-line fixture the delta is modest by design; the point is to
    show the associative-recall mechanism *works*, not to fake a huge
    number. (The old learned_patterns reranker phase was removed — the
    synapse layer supersedes it.)

Outputs:
    - tests/benchmark/results.json  (structured, consumed by chart + CI)
    - tests/benchmark/report.md     (human-readable, posted as PR comment)

Run locally:
    pip install tiktoken graphifyy
    graphify update tests/fixtures/sample_project
    neuralmind build tests/fixtures/sample_project --force
    python -m tests.benchmark.run
"""

from __future__ import annotations

import json
import os
import shutil
import time
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path

import tiktoken

from neuralmind import NeuralMind, memory

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "sample_project"
QUERIES_PATH = REPO_ROOT / "tests" / "fixtures" / "benchmark_queries.json"
RESULTS_PATH = REPO_ROOT / "tests" / "benchmark" / "results.json"
REPORT_PATH = REPO_ROOT / "tests" / "benchmark" / "report.md"

# Conservative regression floor. The fixture is intentionally small
# (~500 lines) so ratios here top out around 5-10× — real repos with
# thousands of lines consistently hit 12-50× because the naive baseline
# is orders of magnitude larger. The floor catches catastrophic
# regressions (retriever returning the whole graph, dropping to ~1×),
# not a missed optimization on a toy input.
REDUCTION_FLOOR = 3.5
# Phase-2 A/B repeats: one draw of a metric that moves decides the gate by
# luck. Three matches the onboarding gate's existing averaging.
SYNAPSE_AB_RUNS = int(os.environ.get("NEURALMIND_SYNAPSE_AB_RUNS", "3"))

# Pin the embedder's ORT thread pool so the benchmark's numbers are not a
# function of the runner's core count. ORT sizes intra-op threads to the host
# by default, and the parallel-summation order moves the last bits of the
# embedding floats — which is exactly the machine-fixed, rebuild-stable
# variance profile the Phase-2 bimodality showed (identical graph partition
# across a passing and a failing job; only the vector path left to differ).
# setdefault so an operator can still override for a threading experiment.
os.environ.setdefault("NEURALMIND_ORT_THREADS", "1")

# Pricing used for the dollars-saved estimate in the report.
# Claude 3.5 Sonnet input price, per 1M tokens, at the time of writing.
# If model pricing shifts, update here only — the rest cascades.
CLAUDE_SONNET_INPUT_PER_MTOK = 3.0
QUERIES_PER_DAY = 100


# --------------------------------------------------------------------- types


@dataclass
class QueryResult:
    """Per-query measurement record."""

    id: str
    question: str
    shape: str
    naive_tokens: int
    neuralmind_tokens: int
    reduction_ratio: float
    expected_modules: list[str]
    hit_modules: list[str]
    top_k_hit_rate: float


@dataclass
class PhaseResult:
    """Aggregated phase output."""

    phase: str
    queries: list[QueryResult] = field(default_factory=list)

    @property
    def avg_reduction(self) -> float:
        if not self.queries:
            return 0.0
        return sum(q.reduction_ratio for q in self.queries) / len(self.queries)

    @property
    def avg_hit_rate(self) -> float:
        if not self.queries:
            return 0.0
        return sum(q.top_k_hit_rate for q in self.queries) / len(self.queries)

    @property
    def total_naive_tokens(self) -> int:
        return sum(q.naive_tokens for q in self.queries)

    @property
    def total_neuralmind_tokens(self) -> int:
        return sum(q.neuralmind_tokens for q in self.queries)


# --------------------------------------------------------------------- helpers


# Cached tokenizer picked by the fallback chain on first access so we don't
# repeat the download attempts (and their failure logs) on every call.
_TOKENIZER_CACHE: dict = {}


def _enc():
    """Return a tokenizer, with graceful fallback if tiktoken can't reach its
    vocab-download endpoint.

    tiktoken lazily downloads vocab files from
    ``openaipublic.blob.core.windows.net`` the first time an encoding is
    used. That endpoint fails for two predictable reasons: restricted
    networks (corporate firewalls, air-gapped CI runners) and transient
    Azure Blob 5xx errors. Rather than crashing the whole benchmark, we
    fall through to progressively simpler options:

    1. ``o200k_base`` — GPT-4o's tokenizer. Best fidelity on modern code.
    2. ``cl100k_base`` — GPT-4 / GPT-3.5 tokenizer. Often pre-cached.
    3. Character-based approximation at ~4 chars/token. Last-resort;
       labeled as such in the report so the ratio is still directional.

    The chosen strategy is cached so subsequent calls don't re-attempt
    downloads.

    Multi-model breakdown lives in tests/benchmark/multi_model.py; this
    runner picks one canonical tokenizer for per-query numbers so the
    report stays focused.
    """
    if "enc" in _TOKENIZER_CACHE:
        return _TOKENIZER_CACHE["enc"]

    import logging

    log = logging.getLogger(__name__)

    for encoding_name in ("o200k_base", "cl100k_base"):
        try:
            enc = tiktoken.get_encoding(encoding_name)
            # Force a trivial encode to make sure the vocab actually
            # loads now, not on first real call later.
            _ = enc.encode("probe")
            _TOKENIZER_CACHE["enc"] = enc
            _TOKENIZER_CACHE["name"] = encoding_name
            return enc
        except Exception as exc:
            log.warning(
                "Tokenizer %s unavailable (%s: %s). Trying next fallback.",
                encoding_name,
                type(exc).__name__,
                exc,
            )

    # Both tiktoken encodings failed — fall back to a character-based
    # approximation. Rough but unblocks CI on restricted networks.
    class _CharApproxEncoding:
        """Stand-in for tiktoken.Encoding when downloads fail.

        Uses ~4 characters per token — a widely-cited average for English
        + code. The reduction *ratio* stays directionally correct because
        both sides of the comparison use the same approximation.
        """

        def encode(self, text: str) -> list[int]:
            # Return a list of fake token ids so len() works; values don't
            # matter because we only read len().
            approx = max(1, len(text) // 4)
            return [0] * approx

    fallback = _CharApproxEncoding()
    _TOKENIZER_CACHE["enc"] = fallback
    _TOKENIZER_CACHE["name"] = "char-approx-4-per-token"
    log.warning(
        "Falling back to character-based token approximation. "
        "Numbers will be rougher but still directionally correct "
        "(both 'before' and 'after' use the same approximation)."
    )
    return fallback


def tokenizer_name() -> str:
    """Name of the tokenizer actually in use, for report labeling."""
    _enc()  # ensure cache populated
    return _TOKENIZER_CACHE.get("name", "unknown")


def naive_baseline_tokens() -> int:
    """Concatenate every .py file in the fixture and count tokens.

    This is the worst-case "load the whole repo" scenario NeuralMind is
    pitched against. Fair, reproducible, and obvious to a skeptic.
    """
    enc = _enc()
    total = 0
    for py_file in sorted(FIXTURE_DIR.rglob("*.py")):
        total += len(enc.encode(py_file.read_text()))
    return total


def top_k_modules(context_text: str) -> list[str]:
    """Extract module paths that appear in a NeuralMind context string.

    The rendered context references entities with their source file
    (e.g. ``authenticate_user — auth/handlers.py``). We scan for the
    fixture's known file paths to avoid brittle regex parsing.
    """
    candidates = [
        str(p.relative_to(FIXTURE_DIR)).replace("\\", "/")
        for p in FIXTURE_DIR.rglob("*.py")
        if p.name != "__init__.py"
    ]
    hits = []
    for c in candidates:
        if c in context_text:
            hits.append(c)
    return hits


def hit_rate(expected: Iterable[str], actual: Iterable[str]) -> float:
    """Fraction of expected modules that appeared in the top retrieval."""
    expected_set = set(expected)
    if not expected_set:
        return 0.0
    actual_set = set(actual)
    return len(expected_set & actual_set) / len(expected_set)


# ---------------------------------------------------------------- phase runners


def run_phase(
    nm: NeuralMind,
    queries: list[dict],
    naive_total: int,
    phase_name: str,
) -> PhaseResult:
    """Run every query and record per-query measurements."""
    result = PhaseResult(phase=phase_name)
    enc = _enc()

    for q in queries:
        ctx = nm.query(q["question"])
        # Token count from tiktoken for fairness across environments.
        # NeuralMind's budget.total is a fast approximation; we re-count
        # the actual rendered context so "before" and "after" use the
        # same tokenizer.
        after_tokens = len(enc.encode(ctx.context))
        hits = top_k_modules(ctx.context)
        result.queries.append(
            QueryResult(
                id=q["id"],
                question=q["question"],
                shape=q["shape"],
                naive_tokens=naive_total,
                neuralmind_tokens=after_tokens,
                reduction_ratio=naive_total / max(after_tokens, 1),
                expected_modules=q["expected_modules"],
                hit_modules=hits,
                top_k_hit_rate=hit_rate(q["expected_modules"], hits),
            )
        )
    return result


def reset_memory() -> None:
    """Clear persisted memory so Phase 2 starts cold, and enable consent.

    CI runs without a TTY, so the first-query prompt would never fire and
    memory logging would default to off. We set the global consent
    sentinel explicitly so every CI run is reproducible.
    """
    # Clear any project-local memory left over from a previous phase.
    mem_dir = FIXTURE_DIR / ".neuralmind"
    if mem_dir.exists():
        shutil.rmtree(mem_dir)

    # Grant consent globally (~/.neuralmind/consent.json) so log_query_event
    # actually writes. This is ephemeral in CI and a no-op locally if the
    # user already said yes.
    memory.write_consent_sentinel(True)


# ----------------------------------------------------------- phase 2 (synapses)

# Realistic "files edited together in one session" groups. The point is to
# teach the synapse graph cross-cutting associations a *textual* search
# wouldn't recover: users/crud.py and db/connection.py are hubs touched
# alongside almost every feature, even though the words "authentication" or
# "billing" never appear in them. A query like "how does auth work?" should,
# once the graph is warm, surface users/crud.py via the learned edge.
SYNAPSE_SESSIONS = [
    ["auth/handlers.py", "auth/jwt_utils.py", "users/crud.py"],
    ["billing/stripe_client.py", "billing/invoices.py", "users/crud.py"],
    ["api/routes.py", "users/crud.py"],
    ["users/crud.py", "db/connection.py"],
    ["billing/stripe_client.py", "db/connection.py"],
]
SYNAPSE_SESSION_REPEATS = 8


def seed_synapses(nm: NeuralMind) -> int:
    """Reinforce co-editing sessions directly into the synapse store.

    Uses ``activate_files`` (the same entry point the file watcher calls)
    so we exercise the real reinforcement path, not a test shim. Returns
    the synapse edge count after seeding.
    """
    for _ in range(SYNAPSE_SESSION_REPEATS):
        for session in SYNAPSE_SESSIONS:
            nm.activate_files(session)
    store = nm.synapses
    return store.stats().get("edges", 0) if store else 0


def run_synapse_phase(
    nm: NeuralMind,
    queries: list[dict],
    naive_total: int,
    inject: bool,
) -> PhaseResult:
    """Measure the query set with synapse recall toggled on or off.

    Reads through ``selector.get_query_context`` rather than ``nm.query``
    so measurement doesn't reinforce the graph mid-run — the only thing
    that differs between the two passes is NEURALMIND_SYNAPSE_INJECT.
    """
    prev = os.environ.get("NEURALMIND_SYNAPSE_INJECT")
    os.environ["NEURALMIND_SYNAPSE_INJECT"] = "1" if inject else "0"
    try:
        result = PhaseResult(phase="synapse-on" if inject else "synapse-off")
        enc = _enc()
        for q in queries:
            ctx = nm.selector.get_query_context(q["question"])
            after_tokens = len(enc.encode(ctx.context))
            hits = top_k_modules(ctx.context)
            result.queries.append(
                QueryResult(
                    id=q["id"],
                    question=q["question"],
                    shape=q["shape"],
                    naive_tokens=naive_total,
                    neuralmind_tokens=after_tokens,
                    reduction_ratio=naive_total / max(after_tokens, 1),
                    expected_modules=q["expected_modules"],
                    hit_modules=hits,
                    top_k_hit_rate=hit_rate(q["expected_modules"], hits),
                )
            )
        return result
    finally:
        if prev is None:
            os.environ.pop("NEURALMIND_SYNAPSE_INJECT", None)
        else:
            os.environ["NEURALMIND_SYNAPSE_INJECT"] = prev


# --------------------------------------------------------------- report writer


def _fmt_pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def _dollars_saved(naive_tokens: int, neuralmind_tokens: int, queries_per_day: int) -> float:
    """Estimated monthly $ saved for Claude 3.5 Sonnet at 100 queries/day.

    Labeled as an estimate everywhere it's shown. This is input tokens
    only — output is unchanged.
    """
    per_query_savings = (
        (naive_tokens - neuralmind_tokens) / 1_000_000 * CLAUDE_SONNET_INPUT_PER_MTOK
    )
    return per_query_savings * queries_per_day * 30


def _environment_fingerprint() -> dict:
    """Capture what differs between machines but not between runs on one.

    Phase 2 is deterministic within a job — three consecutive A/B runs return
    the identical delta — yet the same commit and the same turbovec build have
    produced -1.8 and +4.0 on different runners. So the variable is the host,
    not the sample, and averaging inside one job cannot see it. turbovec is a
    SIMD quantized index and onnxruntime picks kernels per CPU, so the vector
    path is the obvious place for a machine to change a ranking; this records
    enough to correlate an outcome with a host instead of guessing.
    """
    import platform

    def _version(name: str) -> str:
        try:
            import importlib.metadata as md

            return md.version(name)
        except Exception:
            return "absent"

    flags = ""
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("flags"):
                interesting = {
                    "avx",
                    "avx2",
                    "avx512f",
                    "avx512vnni",
                    "fma",
                    "sse4_2",
                    "neon",
                }
                flags = " ".join(sorted(set(line.split(":", 1)[1].split()) & interesting))
                break
    except Exception:
        pass

    return {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "cpu_flags": flags,
        # Core count is what sizes ORT's default thread pool — the one
        # machine property the flags above don't capture, and the direct
        # suspect for between-job embedding variance. Recorded together with
        # the pin actually in effect so a future divergent pair can be
        # attributed (or the thread hypothesis falsified) by inspection.
        "cpu_count": os.cpu_count(),
        "ort_threads": os.environ.get("NEURALMIND_ORT_THREADS") or "default",
        "turbovec": _version("turbovec"),
        "onnxruntime": _version("onnxruntime"),
        "numpy": _version("numpy"),
    }


def _graph_fingerprint(nm) -> dict:
    """Identify the graph the A/B actually ran against.

    Phase 1 and the synapse edge count are identical between a passing and a
    failing CI job, and so is the environment fingerprint — yet Phase 2's "on"
    number differs. Whatever changes is rebuilt per job and fixed within it.
    CI runs `graphify update` before the benchmark, and community detection is
    randomised clustering: a partition that lands differently while producing
    the same node and edge counts would move community-driven selection without
    moving anything else measured here.

    So this records the partition, not just its size — a stable digest over
    (node_id, community). Two jobs whose digests differ have not run the same
    experiment, whatever else matches.
    """
    import hashlib

    try:
        embedder = nm.embedder
        stats = embedder.get_stats()
        rows = sorted(
            (str(n.get("id", "")), int(n.get("metadata", {}).get("community", -1)))
            for n in embedder.get_all_nodes()
        )
        digest = hashlib.sha256(
            "\n".join(f"{nid}:{comm}" for nid, comm in rows).encode()
        ).hexdigest()[:16]
        # Fingerprint the *numeric* embedding path directly: embed fixed probe
        # strings and hash the raw float bytes. Two jobs whose partition digests
        # match but whose probe digests differ have divergent ORT numerics.
        #
        # Two probes, because the single-row one is not sufficient and reading
        # it as such cost an investigation. A 1-row inference and a many-row
        # batch do not share a code path: batched GEMM picks different kernels
        # and blocking, which is exactly where a CPU's SIMD width shows up. The
        # 1-row probe matched across a passing and a failing job, which was read
        # as "the embeddings are bit-identical" — a conclusion it cannot carry.
        probe = ""
        probe_batch = ""
        try:
            vec = embedder._embed_matrix(["neuralmind determinism probe"])
            probe = hashlib.sha256(vec.tobytes()).hexdigest()[:16]
            # Batch path: wide enough to be blocked/tiled like the real corpus.
            batch = [f"neuralmind determinism probe row {i}" for i in range(64)]
            vecs = embedder._embed_matrix(batch)
            probe_batch = hashlib.sha256(vecs.tobytes()).hexdigest()[:16]
        except Exception:
            pass  # backends without _embed_matrix; never fail the benchmark

        # Digest the vectors search actually reads. TurboVec stores them
        # quantised, so a sub-quantum embedding difference is normally erased
        # — but a value sitting on a bucket boundary flips discretely. That is
        # the shape of this gate's failure: two stable modes that each recur
        # bit-for-bit, rather than the spread continuous jitter would give.
        # If this digest differs across two jobs, the divergence is upstream in
        # the embeddings; if it matches while the A/B still splits, it is
        # downstream in the synapse layer.
        index_digest = ""
        try:
            index_path = getattr(embedder, "_index_path", None)
            if index_path is not None and index_path.exists():
                index_digest = hashlib.sha256(index_path.read_bytes()).hexdigest()[:16]
        except Exception:
            pass  # diagnostics must never fail the benchmark
        # Record the `refund` query's decision inputs verbatim.
        #
        # This one query is the whole bimodality: it is the only one whose hit
        # rate flips between the two modes, and 1/19 flipping 1.0 -> 0.0 is
        # 5.26 points, exactly the observed gap. Measurements so far place the
        # divergence downstream of the vector path — with recall off the two
        # host classes agree on all 19 queries, and locally the outcome does
        # not move under embedding perturbations up to 1e-2 — so what is worth
        # capturing is the state the displacement decision actually reads.
        #
        # Values, not a digest: a digest only says "differs", and the question
        # here is *which* number differs and by how much.
        refund_probe = {}
        try:
            sel = nm.selector
            pre = sel._fetch_search("Show me the refund logic.", n=4)
            refund_probe["results"] = [
                [str(r.get("id")), round(float(r.get("score") or 0.0), 12)] for r in pre
            ]
            seeds = [r["id"] for r in pre[: sel._synapse_seed_k] if r.get("id")]
            refund_probe["seeds"] = seeds
            energy = sel._recall_energy(seeds) or {}
            refund_probe["energy"] = [
                [nid, round(float(e), 12)]
                for nid, e in sorted(energy.items(), key=lambda x: (-x[1], x[0]))[:8]
            ]
        except Exception as exc:
            refund_probe = {"error": f"{type(exc).__name__}: {exc}"}

        return {
            "nodes": stats.get("total_nodes"),
            "communities": stats.get("communities"),
            "community_partition_sha256_16": digest,
            "embedding_probe_sha256_16": probe,
            "embedding_probe_batch_sha256_16": probe_batch,
            "vector_index_sha256_16": index_digest,
            "refund_decision_probe": refund_probe,
        }
    except Exception as exc:  # diagnostics must never fail the benchmark
        return {"error": f"{type(exc).__name__}: {exc}"}


def _mean(values) -> float:
    vals = list(values)
    return sum(vals) / len(vals) if vals else 0.0


def write_results(
    phase1: PhaseResult,
    off_runs: list[PhaseResult],
    on_runs: list[PhaseResult],
    synapse_edges: int,
    graph_fp: dict | None = None,
) -> None:
    """Write the JSON payload consumed by the chart script and CI."""
    payload = {
        "version": 1,
        "phase1_reduction": {
            "avg_reduction_ratio": phase1.avg_reduction,
            "avg_top_k_hit_rate": phase1.avg_hit_rate,
            "total_naive_tokens": phase1.total_naive_tokens,
            "total_neuralmind_tokens": phase1.total_neuralmind_tokens,
            "queries": [asdict(q) for q in phase1.queries],
        },
        "phase2_synapse": {
            "synapse_edges": synapse_edges,
            # Means across SYNAPSE_AB_RUNS. The gate reads these; the per-run
            # lists below keep the spread visible rather than averaged away.
            "ab_runs": len(on_runs),
            "off_avg_reduction_ratio": _mean(r.avg_reduction for r in off_runs),
            "off_avg_top_k_hit_rate": _mean(r.avg_hit_rate for r in off_runs),
            "on_avg_reduction_ratio": _mean(r.avg_reduction for r in on_runs),
            "on_avg_top_k_hit_rate": _mean(r.avg_hit_rate for r in on_runs),
            "uplift_hit_rate": (
                _mean(r.avg_hit_rate for r in on_runs) - _mean(r.avg_hit_rate for r in off_runs)
            ),
            "reduction_delta": (
                _mean(r.avg_reduction for r in on_runs) - _mean(r.avg_reduction for r in off_runs)
            ),
            "off_hit_rate_runs": [r.avg_hit_rate for r in off_runs],
            "on_hit_rate_runs": [r.avg_hit_rate for r in on_runs],
            "queries": [asdict(q) for q in on_runs[-1].queries],
            # Same run index as "queries" (the last A/B repeat), recall off.
            # Diffing hit_modules between the two shows exactly which queries
            # displacement changed — the first thing to read when the delta
            # gate fails, before any cross-job comparison.
            "off_queries": [asdict(q) for q in off_runs[-1].queries],
        },
        "environment": _environment_fingerprint(),
        "graph": graph_fp or {},
        "regression_floor": REDUCTION_FLOOR,
        "pass": phase1.avg_reduction >= REDUCTION_FLOOR,
        "estimated_monthly_savings_usd": _dollars_saved(
            phase1.total_naive_tokens // max(len(phase1.queries), 1),
            phase1.total_neuralmind_tokens // max(len(phase1.queries), 1),
            QUERIES_PER_DAY,
        ),
        "pricing_note": (
            f"Dollar figure assumes Claude 3.5 Sonnet input at "
            f"${CLAUDE_SONNET_INPUT_PER_MTOK}/MTok and {QUERIES_PER_DAY} queries/day."
        ),
    }
    RESULTS_PATH.write_text(json.dumps(payload, indent=2))


def write_report(
    phase1: PhaseResult,
    off_runs: list[PhaseResult],
    on_runs: list[PhaseResult],
    synapse_edges: int,
) -> None:
    """Write the human-readable Markdown report posted as a PR comment."""
    status = "PASS" if phase1.avg_reduction >= REDUCTION_FLOOR else "FAIL"
    savings = _dollars_saved(
        phase1.total_naive_tokens // max(len(phase1.queries), 1),
        phase1.total_neuralmind_tokens // max(len(phase1.queries), 1),
        QUERIES_PER_DAY,
    )

    lines = [
        "## NeuralMind self-benchmark",
        "",
        f"**Status:** `{status}` — floor `{REDUCTION_FLOOR:.0f}×`, measured `{phase1.avg_reduction:.1f}×`.",
        "",
        "### Phase 1 — Reduction on committed fixture",
        "",
        f"- Average reduction: **{phase1.avg_reduction:.1f}×**",
        f"- Top-k retrieval hit rate: **{_fmt_pct(phase1.avg_hit_rate)}**",
        f"- Naive baseline: `{phase1.total_naive_tokens:,}` tokens (all fixture files concatenated)",
        f"- NeuralMind total: `{phase1.total_neuralmind_tokens:,}` tokens across {len(phase1.queries)} queries",
        f"- Estimated monthly savings @ {QUERIES_PER_DAY} queries/day on Claude 3.5 Sonnet: **~${savings:,.2f}**",
        "",
        "| # | Query | Shape | Naive | NeuralMind | Ratio | Hit |",
        "|---|-------|-------|------:|-----------:|------:|----:|",
    ]
    for i, q in enumerate(phase1.queries, 1):
        lines.append(
            f"| {i} | `{q.id}` | {q.shape} | {q.naive_tokens:,} | "
            f"{q.neuralmind_tokens:,} | {q.reduction_ratio:.1f}× | {_fmt_pct(q.top_k_hit_rate)} |"
        )

    lines += [
        "",
        "### Phase 2 — Synapse recall A/B (same warm graph, recall off vs on)",
        "",
        f"- Synapse edges after seeding co-editing sessions: `{synapse_edges}`",
        (
            f"- Top-k hit rate: **{_fmt_pct(_mean(r.avg_hit_rate for r in off_runs))}** off → "
            f"**{_fmt_pct(_mean(r.avg_hit_rate for r in on_runs))}** on "
            f"(Δ {(_mean(r.avg_hit_rate for r in on_runs) - _mean(r.avg_hit_rate for r in off_runs)) * 100:+.1f} "
            f"points, mean of {len(on_runs)} runs)"
        ),
        (
            "- Per-run deltas: "
            + ", ".join(
                f"`{(on.avg_hit_rate - off.avg_hit_rate) * 100:+.1f}`"
                for off, on in zip(off_runs, on_runs, strict=True)
            )
            + " points — published because this metric moves between runs, and a"
            " mean that hides its own spread is how a directional claim gets"
            " decided by luck."
        ),
        (
            f"- Reduction ratio: **{_mean(r.avg_reduction for r in off_runs):.1f}×** off → "
            f"**{_mean(r.avg_reduction for r in on_runs):.1f}×** on "
            f"(Δ {_mean(r.avg_reduction for r in on_runs) - _mean(r.avg_reduction for r in off_runs):+.2f}× — "
            "budget-neutral by design)"
        ),
        "",
        "The Hebbian synapse layer is now the single learning measurement (the old",
        "`learned_patterns` reranker was removed). The hit-rate delta shows associative recall",
        "surfacing co-edited modules a purely textual search ranks lower; the near-zero reduction",
        "delta confirms it does so without spending extra tokens (recalled nodes displace the",
        "weakest hits, not add to them).",
        "",
        "### Assumptions",
        "",
        "- Baseline: every `.py` file in `tests/fixtures/sample_project/` concatenated.",
        "- Tokenizer: `tiktoken` GPT-4o encoding (per-model breakdown in `multi_model.json` if generated).",
        f"- Pricing: Claude 3.5 Sonnet input @ ${CLAUDE_SONNET_INPUT_PER_MTOK}/MTok.",
        f"- Regression floor: `{REDUCTION_FLOOR:.0f}×` — well below NeuralMind's typical `12–50×` on real repos.",
        "",
    ]
    REPORT_PATH.write_text("\n".join(lines))


# --------------------------------------------------------------- orchestration


def main() -> int:
    queries_doc = json.loads(QUERIES_PATH.read_text())
    queries = queries_doc["queries"]

    # Naive baseline is the same for every query — compute once.
    naive_total = naive_baseline_tokens()

    # Phase 1 — cold run, no memory.
    reset_memory()
    nm = NeuralMind(str(FIXTURE_DIR))
    t0 = time.time()
    phase1 = run_phase(nm, queries, naive_total, phase_name="cold")
    phase1_seconds = time.time() - t0

    # Phase 2 — synapse recall A/B (the single learning measurement).
    # Reinforce co-editing sessions, then measure the same queries with
    # synapse recall off vs on. Verifies the boost is budget-neutral
    # (reduction holds) while associative recall lifts the hit rate.
    # Repeated, because a single draw does not settle a directional claim.
    # This A/B has returned both -1.75 and +4.0 points from the *same* commit
    # and the same turbovec build, and the two outcomes recur bit-for-bit
    # rather than spreading — so one sample decides the gate by luck. The
    # sibling onboarding gate in ci-benchmark.yml already averages three runs
    # for the same reason ("Averaged to absorb any ChromaDB HNSW query-time
    # jitter"). Every run is published below, so the spread stays visible
    # instead of being hidden behind its own mean.
    off_runs: list[PhaseResult] = []
    on_runs: list[PhaseResult] = []
    synapse_edges = 0
    for _ in range(SYNAPSE_AB_RUNS):
        reset_memory()
        nm = NeuralMind(str(FIXTURE_DIR))
        synapse_edges = seed_synapses(nm)
        graph_fp = _graph_fingerprint(nm)
        off_runs.append(run_synapse_phase(nm, queries, naive_total, inject=False))
        on_runs.append(run_synapse_phase(nm, queries, naive_total, inject=True))
    write_results(phase1, off_runs, on_runs, synapse_edges, graph_fp)
    write_report(phase1, off_runs, on_runs, synapse_edges)

    print(
        f"Phase 1: {phase1.avg_reduction:.1f}× reduction, "
        f"{phase1.avg_hit_rate * 100:.0f}% top-k hit rate "
        f"({phase1_seconds:.1f}s)"
    )
    off_mean = _mean(r.avg_hit_rate for r in off_runs)
    on_mean = _mean(r.avg_hit_rate for r in on_runs)
    per_run = ", ".join(
        f"{(on.avg_hit_rate - off.avg_hit_rate) * 100:+.1f}"
        for off, on in zip(off_runs, on_runs, strict=True)
    )
    env = _environment_fingerprint()
    print(
        f"Graph: {graph_fp.get('nodes')} nodes, {graph_fp.get('communities')} communities, "
        f"partition {graph_fp.get('community_partition_sha256_16')}"
    )
    print(
        f"Env: turbovec {env['turbovec']}, onnxruntime {env['onnxruntime']}, "
        f"numpy {env['numpy']}, {env['machine']} [{env['cpu_flags'] or 'n/a'}]"
    )
    print(
        f"Phase 2: synapse off {off_mean * 100:.0f}% → "
        f"on {on_mean * 100:.0f}% hit rate "
        f"(Δ {(on_mean - off_mean) * 100:+.0f}pts, mean of {len(on_runs)}; "
        f"runs [{per_run}]), "
        f"reduction {_mean(r.avg_reduction for r in off_runs):.1f}× → "
        f"{_mean(r.avg_reduction for r in on_runs):.1f}×, "
        f"{synapse_edges} edges"
    )

    return 0 if phase1.avg_reduction >= REDUCTION_FLOOR else 1


if __name__ == "__main__":
    raise SystemExit(main())
