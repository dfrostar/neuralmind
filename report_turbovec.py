#!/usr/bin/env python3
"""report_turbovec.py — render a Markdown report from benchmark_turbovec.py JSON.

    python report_turbovec.py results.json --out report.md

The report contains:

* **A one-line verdict** — 🟢 yes / 🟡 cautiously yes / 🛑 not yet / ⚪
  inconclusive — derived from parity *and* performance signals.
* **Environment provenance** — versions, platform, CPU count, repo size.
* **Headline table** — indexing latency, search p50/p95/mean, on-disk size,
  peak RSS, with signed-percent deltas (turbovec vs. chroma).
* **Parity section** — mean Jaccard@k, recall of chroma's top-k by turbovec,
  and a (collapsed) per-query overlap table.
* **Per-query latency table** — side-by-side ms so a single regressing query
  type is visible.
* **Caveats** — first-run model download, what tracemalloc does/doesn't
  capture, the experimental/POC label on turbovec.

It is dependency-free (stdlib only) so it runs anywhere the JSON lands.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

BASELINE = "chroma"  # deltas are computed as candidate-vs-baseline
CANDIDATE = "turbovec"


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def pct_delta(candidate: float, baseline: float) -> str:
    """Signed percent change of candidate relative to baseline, as a string."""
    if baseline == 0:
        return "n/a"
    delta = (candidate - baseline) / baseline * 100.0
    sign = "+" if delta >= 0 else ""
    return f"{sign}{delta:.1f}%"


def jaccard(a: list[str], b: list[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 1.0
    union = sa | sb
    return len(sa & sb) / len(union) if union else 1.0


def recall_of(reference: list[str], candidate: list[str]) -> float:
    """Fraction of reference ids recovered by candidate."""
    sr = set(reference)
    if not sr:
        return 1.0
    return len(sr & set(candidate)) / len(sr)


def fmt_mb(byte_count: float | int | None) -> str:
    if byte_count is None:
        return "—"
    return f"{byte_count / 1e6:.1f} MB"


def fmt_ms(value: float | None) -> str:
    return "—" if value is None else f"{value:.2f}"


def fmt_num(value) -> str:
    return "—" if value is None else str(value)


# --------------------------------------------------------------------------- #
# Verdict
# --------------------------------------------------------------------------- #
def compute_verdict(parity: dict, headline: dict, both_ok: bool) -> tuple[str, str]:
    if not both_ok:
        return ("⚪ inconclusive", "One or both backends failed to complete — see the run log.")

    jacc = parity["mean_jaccard"]
    recall = parity["mean_recall"]

    # Performance signals: lower is better for latency/disk/RSS.
    search_p95 = headline["search_p95_delta_pct"]
    disk = headline["disk_delta_pct"]
    rss = headline["rss_delta_pct"]

    perf_regressions = []
    if search_p95 is not None and search_p95 > 10:
        perf_regressions.append(f"search p95 {search_p95:+.0f}%")
    if rss is not None and rss > 20:
        perf_regressions.append(f"peak RSS {rss:+.0f}%")
    if disk is not None and disk > 0:
        perf_regressions.append(f"on-disk {disk:+.0f}%")

    parity_good = jacc >= 0.70 and recall >= 0.80
    parity_marginal = jacc >= 0.50 and recall >= 0.60

    if parity_good and not perf_regressions:
        return (
            "🟢 yes",
            f"turbovec is at parity (Jaccard@k {jacc:.2f}, recall {recall:.2f}) with no "
            "performance regression — safe to adopt for this workload.",
        )
    if parity_good and perf_regressions:
        return (
            "🟡 cautiously yes",
            f"parity holds (Jaccard@k {jacc:.2f}, recall {recall:.2f}) but watch: "
            + ", ".join(perf_regressions)
            + ".",
        )
    if parity_marginal:
        return (
            "🟡 cautiously yes",
            f"parity is marginal (Jaccard@k {jacc:.2f}, recall {recall:.2f}); "
            "validate against the gold-set eval before relying on it.",
        )
    return (
        "🛑 not yet",
        f"parity is below tolerance (Jaccard@k {jacc:.2f}, recall {recall:.2f}); "
        "results diverge too much from chroma for this workload.",
    )


# --------------------------------------------------------------------------- #
# Report assembly
# --------------------------------------------------------------------------- #
def build_report(data: dict) -> str:
    env = data.get("environment", {})
    cfg = data.get("config", {})
    results = data.get("results", {})
    base = results.get(BASELINE, {})
    cand = results.get(CANDIDATE, {})
    both_ok = bool(base.get("ok")) and bool(cand.get("ok"))

    # ---- Parity (only meaningful if both ran) ------------------------------ #
    parity = {"mean_jaccard": 0.0, "mean_recall": 0.0, "rows": []}
    if both_ok:
        bq = {row["query"]: row for row in base.get("per_query", [])}
        cq = {row["query"]: row for row in cand.get("per_query", [])}
        jaccs, recalls = [], []
        for q in cfg.get("queries", []):
            b_ids = bq.get(q, {}).get("top_ids", [])
            c_ids = cq.get(q, {}).get("top_ids", [])
            j = jaccard(b_ids, c_ids)
            r = recall_of(b_ids, c_ids)
            jaccs.append(j)
            recalls.append(r)
            parity["rows"].append({"query": q, "jaccard": j, "recall": r})
        parity["mean_jaccard"] = sum(jaccs) / len(jaccs) if jaccs else 0.0
        parity["mean_recall"] = sum(recalls) / len(recalls) if recalls else 0.0

    # ---- Headline deltas --------------------------------------------------- #
    def g(d: dict, *path, default=None):
        cur = d
        for key in path:
            if not isinstance(cur, dict):
                return default
            cur = cur.get(key, default)
        return cur

    headline = {
        "search_p95_delta_pct": None,
        "disk_delta_pct": None,
        "rss_delta_pct": None,
    }
    if both_ok:
        b_p95 = g(base, "search", "ms_p95", default=0.0)
        c_p95 = g(cand, "search", "ms_p95", default=0.0)
        headline["search_p95_delta_pct"] = (
            (c_p95 - b_p95) / b_p95 * 100.0 if b_p95 else None
        )
        b_disk = base.get("disk_bytes", 0) or 0
        c_disk = cand.get("disk_bytes", 0) or 0
        headline["disk_delta_pct"] = (
            (c_disk - b_disk) / b_disk * 100.0 if b_disk else None
        )
        b_rss = base.get("peak_rss_mb", 0) or 0
        c_rss = cand.get("peak_rss_mb", 0) or 0
        headline["rss_delta_pct"] = (
            (c_rss - b_rss) / b_rss * 100.0 if b_rss else None
        )

    verdict, rationale = compute_verdict(parity, headline, both_ok)

    # ---- Markdown ---------------------------------------------------------- #
    out: list[str] = []
    out.append("# TurboVec vs. ChromaDB — memory/latency benchmark")
    out.append("")
    out.append(f"**Verdict: {verdict}** — {rationale}")
    out.append("")
    out.append(f"_Generated from `{data.get('generated_at', 'unknown time')}` run._")
    out.append("")

    # Environment
    out.append("## Environment")
    out.append("")
    out.append("| | |")
    out.append("|---|---|")
    rows = [
        ("neuralmind", env.get("neuralmind")),
        ("turbovec", env.get("turbovec")),
        ("chromadb", env.get("chromadb")),
        ("onnxruntime", env.get("onnxruntime")),
        ("tokenizers", env.get("tokenizers")),
        ("numpy", env.get("numpy")),
        ("Python", env.get("python")),
        ("platform", env.get("platform")),
        ("CPU count", env.get("cpu_count")),
        ("repo", env.get("repo")),
        ("source files", env.get("source_files")),
        ("graph nodes", env.get("graph_nodes")),
        ("graph links", env.get("graph_links")),
    ]
    for k, v in rows:
        out.append(f"| {k} | {fmt_num(v)} |")
    out.append("")
    out.append(
        f"_Config: top_k={cfg.get('top_k')}, repeat={cfg.get('repeat')}, "
        f"warmup={cfg.get('warmup')}, queries={len(cfg.get('queries', []))}, "
        f"synthetic={cfg.get('synthetic')}._"
    )
    out.append("")

    # Headline table
    out.append("## Headline")
    out.append("")
    out.append(f"| metric | {BASELINE} | {CANDIDATE} | Δ ({CANDIDATE} vs {BASELINE}) |")
    out.append("|---|---:|---:|---:|")

    def hrow(label, b_val, c_val, fmt, delta_str):
        out.append(f"| {label} | {fmt(b_val)} | {fmt(c_val)} | {delta_str} |")

    if both_ok:
        hrow(
            "indexing latency (s)",
            base.get("index_seconds"),
            cand.get("index_seconds"),
            lambda v: fmt_ms(v),
            pct_delta(cand.get("index_seconds", 0), base.get("index_seconds", 0)),
        )
        hrow(
            "search p50 (ms)",
            g(base, "search", "ms_p50"),
            g(cand, "search", "ms_p50"),
            fmt_ms,
            pct_delta(g(cand, "search", "ms_p50", default=0), g(base, "search", "ms_p50", default=0)),
        )
        hrow(
            "search p95 (ms)",
            g(base, "search", "ms_p95"),
            g(cand, "search", "ms_p95"),
            fmt_ms,
            pct_delta(g(cand, "search", "ms_p95", default=0), g(base, "search", "ms_p95", default=0)),
        )
        hrow(
            "search mean (ms)",
            g(base, "search", "ms_mean"),
            g(cand, "search", "ms_mean"),
            fmt_ms,
            pct_delta(g(cand, "search", "ms_mean", default=0), g(base, "search", "ms_mean", default=0)),
        )
        hrow(
            "on-disk size",
            base.get("disk_bytes"),
            cand.get("disk_bytes"),
            fmt_mb,
            pct_delta(cand.get("disk_bytes", 0), base.get("disk_bytes", 0)),
        )
        hrow(
            "peak RSS",
            base.get("peak_rss_mb"),
            cand.get("peak_rss_mb"),
            lambda v: "—" if v is None else f"{v:.1f} MB",
            pct_delta(cand.get("peak_rss_mb", 0), base.get("peak_rss_mb", 0)),
        )
        hrow(
            "tracemalloc peak (Python)",
            base.get("tracemalloc_peak_mb"),
            cand.get("tracemalloc_peak_mb"),
            lambda v: "—" if v is None else f"{v:.1f} MB",
            pct_delta(cand.get("tracemalloc_peak_mb", 0), base.get("tracemalloc_peak_mb", 0)),
        )
    else:
        out.append("| _backend(s) failed — see below_ | | | |")
    out.append("")
    out.append(
        "_Negative Δ favours turbovec for latency/size/memory. Peak RSS is the "
        "ground-truth memory number; tracemalloc only sees Python objects._"
    )
    out.append("")

    # Failures
    for name, res in results.items():
        if not res.get("ok"):
            out.append(f"### ⚠️ Backend `{name}` failed")
            out.append("")
            out.append(f"```\n{res.get('error', 'unknown error')}\n```")
            out.append("")

    # Parity
    if both_ok:
        out.append("## Parity (turbovec vs. chroma top-k)")
        out.append("")
        out.append(f"- **Mean Jaccard@{cfg.get('top_k')}:** {parity['mean_jaccard']:.3f}")
        out.append(
            f"- **Mean recall of chroma's top-k by turbovec:** {parity['mean_recall']:.3f}"
        )
        out.append("")
        out.append("<details><summary>Per-query overlap</summary>")
        out.append("")
        out.append("| query | Jaccard | recall |")
        out.append("|---|---:|---:|")
        for row in parity["rows"]:
            out.append(f"| {row['query']} | {row['jaccard']:.2f} | {row['recall']:.2f} |")
        out.append("")
        out.append("</details>")
        out.append("")

        # Per-query latency
        out.append("## Per-query latency (ms)")
        out.append("")
        out.append(
            f"| query | {BASELINE} p50 | {CANDIDATE} p50 | {BASELINE} p95 | {CANDIDATE} p95 |"
        )
        out.append("|---|---:|---:|---:|---:|")
        bq = {row["query"]: row for row in base.get("per_query", [])}
        cq = {row["query"]: row for row in cand.get("per_query", [])}
        for q in cfg.get("queries", []):
            b = bq.get(q, {})
            c = cq.get(q, {})
            out.append(
                f"| {q} | {fmt_ms(b.get('ms_p50'))} | {fmt_ms(c.get('ms_p50'))} | "
                f"{fmt_ms(b.get('ms_p95'))} | {fmt_ms(c.get('ms_p95'))} |"
            )
        out.append("")

    # Caveats
    out.append("## Caveats")
    out.append("")
    out.append(
        "- **First-run model download.** turbovec's first run fetches the "
        "`all-MiniLM-L6-v2` ONNX model (~90 MB) unless `NEURALMIND_ONNX_MODEL_DIR` "
        "is pre-staged. Both backends share the same model, so warm-run latency "
        "excludes this."
    )
    out.append(
        "- **tracemalloc only sees Python allocations.** numpy buffers, "
        "onnxruntime's session arena, and SQLite page cache show up in RSS but "
        "not tracemalloc. Trust the **peak RSS** number for real memory cost; "
        "treat tracemalloc as a hint about the Python-object share."
    )
    out.append(
        "- **`ru_maxrss` units differ** (KB on Linux, bytes on macOS) — the "
        "benchmark normalises to MB before reporting."
    )
    out.append(
        "- **Recall here is recall-vs-chroma**, which assumes chroma is correct. "
        "For ground-truth recall run NeuralMind's gold-set eval (`evals/`)."
    )
    out.append(
        "- **turbovec is experimental (POC, issue #204).** This is a single-"
        "threaded, warm-cache, query-level sanity check — not a replacement for "
        "the faithfulness gold set, and it doesn't measure concurrent load."
    )
    out.append("")

    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("results", help="results JSON from benchmark_turbovec.py")
    parser.add_argument("--out", default="report.md", help="output Markdown path")
    args = parser.parse_args(argv)

    data = json.loads(Path(args.results).read_text(encoding="utf-8"))
    report = build_report(data)

    out = Path(args.out)
    out.write_text(report, encoding="utf-8")
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
