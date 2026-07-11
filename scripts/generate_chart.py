"""Render the benchmark results as a PNG for the README.

Reads ``tests/benchmark/multi_model.json`` (per-model reduction ratios
produced by ``tests/benchmark/multi_model.py``) and writes a dark-themed
bar chart to ``docs/images/benchmark_chart.png``.

Rules:

- Every bar's number comes straight from the JSON. No hardcoded values.
- Bars for **estimated** models are drawn with a hatched pattern and
  include an asterisk in the label so the distinction is visible.
- Chart title cites the fixture path + commit short SHA if available,
  so the image is self-dating — a reader can always trace it back to
  the commit that produced it.

Run after the benchmark:
    python -m tests.benchmark.run
    python -m tests.benchmark.multi_model
    python scripts/generate_chart.py
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Patch

REPO_ROOT = Path(__file__).resolve().parents[1]
MULTI_MODEL_PATH = REPO_ROOT / "tests" / "benchmark" / "multi_model.json"
RESULTS_PATH = REPO_ROOT / "tests" / "benchmark" / "results.json"
OUT_PATH = REPO_ROOT / "docs" / "images" / "benchmark_chart.png"


def _git_short_sha() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO_ROOT,
            stderr=subprocess.DEVNULL,
        )
        return out.decode().strip()
    except Exception:
        return "local"


def render() -> None:
    if not MULTI_MODEL_PATH.exists():
        raise FileNotFoundError(f"{MULTI_MODEL_PATH} missing — run multi_model.py first.")
    data = json.loads(MULTI_MODEL_PATH.read_text())
    rows = data["models"]
    if not rows:
        raise RuntimeError("multi_model.json contained no measurements.")

    # Pull the Phase 1 aggregate ratio for the headline, if available.
    avg_ratio = None
    total_naive = total_nm = None
    if RESULTS_PATH.exists():
        results = json.loads(RESULTS_PATH.read_text())
        phase1 = results.get("phase1_reduction", {})
        avg_ratio = phase1.get("avg_reduction_ratio")
        total_naive = phase1.get("total_naive_tokens")
        total_nm = phase1.get("total_neuralmind_tokens")

    labels = [r["model"] + ("*" if not r["measured"] else "") for r in rows]
    ratios = [r["reduction_ratio"] for r in rows]
    measured_flags = [r["measured"] for r in rows]

    plt.style.use("dark_background")
    fig, ax = plt.subplots(figsize=(11, 6.2))
    fig.patch.set_facecolor("#140526")
    ax.set_facecolor("#140526")

    palette_measured = "#00e5ff"
    palette_estimated = "#6c4aff"

    bars = ax.bar(
        labels,
        ratios,
        color=[palette_measured if m else palette_estimated for m in measured_flags],
        edgecolor="white",
        linewidth=0.6,
    )
    # Hatch pattern for estimated bars — a second visual cue.
    for bar, m in zip(bars, measured_flags, strict=True):
        if not m:
            bar.set_hatch("//")

    max_ratio = max(ratios)
    ax.set_ylim(0, max_ratio * 1.25)
    ax.set_ylabel("Reduction ratio (×)", color="#d6ccec", fontsize=11)
    ax.tick_params(axis="x", colors="#d6ccec")
    ax.tick_params(axis="y", colors="#8d82a8")
    for spine in ax.spines.values():
        spine.set_color("#2a2927")

    headline = "NeuralMind token reduction by tokenizer"
    subtitle = f"fixture: tests/fixtures/sample_project @ {_git_short_sha()}"
    if avg_ratio is not None and total_naive and total_nm:
        subtitle += f"   •   aggregate {avg_ratio:.1f}×   •   {total_naive:,} → {total_nm:,} tokens"
    ax.set_title(headline, color="white", fontsize=15, pad=14, fontweight="bold")
    fig.text(
        0.5,
        0.91,
        subtitle,
        ha="center",
        fontsize=9,
        color="#8d82a8",
    )

    # Value labels on each bar.
    for bar, r in zip(bars, ratios, strict=True):
        ax.text(
            bar.get_x() + bar.get_width() / 2.0,
            bar.get_height() + max_ratio * 0.03,
            f"{r:.1f}×",
            ha="center",
            va="bottom",
            color="white",
            fontsize=11,
            fontweight="bold",
        )

    legend_handles = [
        Patch(facecolor=palette_measured, edgecolor="white", label="measured (real tokenizer)"),
        Patch(
            facecolor=palette_estimated,
            edgecolor="white",
            hatch="//",
            label="estimated (published vocab ratio)",
        ),
    ]
    ax.legend(
        handles=legend_handles,
        loc="upper right",
        frameon=False,
        labelcolor="#d6ccec",
        fontsize=9,
    )

    fig.tight_layout(rect=(0, 0, 1, 0.90))
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_PATH, dpi=160, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    render()
