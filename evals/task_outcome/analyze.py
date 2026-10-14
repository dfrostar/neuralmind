"""Paired statistics and the pre-registered decision rule.

    python -m evals.task_outcome.analyze bench/task_outcome/pilot [--json]

The unit of analysis is the task: each arm's runs on a task are averaged, so
the two arms are compared on the same tasks (a paired design), and repeated
seeds reduce agent noise without inflating n.

Endpoints, fixed in docs/specs/TASK-OUTCOME-BENCHMARK-SPEC.md before any run:

* **Primary, cost.** Per task, d = mean cost with NeuralMind minus mean cost
  without. One-sided Wilcoxon signed-rank test that d is centred below zero,
  exact distribution (sign flips over the observed ranks, ties averaged,
  zeros dropped).
* **Co-primary, solve rate.** A task counts as solved by an arm when most of
  its seeds solve it. Exact two-sided McNemar test on the discordant tasks.
* **Effect size.** Median per-task relative cost change, d / baseline cost,
  with a 95% bootstrap interval over tasks (seeded, so the report reproduces).

The claim "NeuralMind lowers the agent's cost per task without lowering its
solve rate" is made only when all three hold: the Wilcoxon p < 0.05, the
interval's upper bound is below zero, and NeuralMind solves no fewer tasks
than the baseline minus the pre-registered margin. Anything else is reported
as what it is: no effect shown, or a loss.

Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from math import comb
from pathlib import Path

ALPHA = 0.05
NONINFERIORITY_TASKS = 1  # NeuralMind may solve at most this many fewer tasks
BOOTSTRAP_SAMPLES = 10_000
BOOTSTRAP_SEED = 20261014


def wilcoxon_signed_rank(diffs: list[float]) -> dict:
    """Exact Wilcoxon signed-rank test. ``p_less`` tests median < 0."""
    nonzero = [d for d in diffs if d != 0]
    n = len(nonzero)
    if n == 0:
        return {"n": 0, "w_plus": 0.0, "p_less": 1.0, "p_greater": 1.0}
    order = sorted(range(n), key=lambda i: abs(nonzero[i]))
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and abs(nonzero[order[j + 1]]) == abs(nonzero[order[i]]):
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2 + 1  # average rank for ties
        i = j + 1
    w_plus = sum(r for r, d in zip(ranks, nonzero, strict=True) if d > 0)
    # Exact null distribution of W+ under random signs. Ranks are multiples of
    # 0.5, so work in half-units to keep the DP over integers.
    halves = [round(r * 2) for r in ranks]
    total = sum(halves)
    dist = [0] * (total + 1)
    dist[0] = 1
    for h in halves:
        for s in range(total, h - 1, -1):
            dist[s] += dist[s - h]
    count = 2**n
    obs = round(w_plus * 2)
    p_less = sum(dist[: obs + 1]) / count
    p_greater = sum(dist[obs:]) / count
    return {"n": n, "w_plus": w_plus, "p_less": p_less, "p_greater": p_greater}


def mcnemar_exact(only_baseline: int, only_neuralmind: int) -> float:
    """Two-sided exact McNemar p-value from the two discordant counts."""
    n = only_baseline + only_neuralmind
    if n == 0:
        return 1.0
    k = min(only_baseline, only_neuralmind)
    tail = sum(comb(n, i) for i in range(k + 1)) / 2**n
    return min(1.0, 2 * tail)


def bootstrap_ci(values: list[float], stat=statistics.median, level: float = 0.95) -> tuple:
    if not values:
        return (None, None)
    rng = random.Random(BOOTSTRAP_SEED)
    samples = sorted(stat([rng.choice(values) for _ in values]) for _ in range(BOOTSTRAP_SAMPLES))
    lo = samples[int((1 - level) / 2 * BOOTSTRAP_SAMPLES)]
    hi = samples[int((1 + level) / 2 * BOOTSTRAP_SAMPLES) - 1]
    return (lo, hi)


def per_task(runs: list[dict]) -> dict[str, dict[str, dict]]:
    """``{task: {arm: {cost, solved_share, solved_majority, explore, turns, n}}}``."""
    grouped: dict[str, dict[str, list[dict]]] = {}
    for r in runs:
        grouped.setdefault(r["task"], {}).setdefault(r["arm"], []).append(r)
    out: dict[str, dict[str, dict]] = {}
    for task, arms in grouped.items():
        out[task] = {}
        for arm, rs in arms.items():
            costs = [r["cost_usd"] for r in rs if r.get("cost_usd") is not None]
            solved = [bool(r.get("solved")) for r in rs]
            out[task][arm] = {
                "n": len(rs),
                "cost": statistics.fmean(costs) if costs else None,
                "solved_share": sum(solved) / len(solved),
                "solved_majority": sum(solved) * 2 > len(solved),
                "explore": statistics.fmean(
                    r.get("explore_calls_before_first_edit", 0) for r in rs
                ),
                "turns": statistics.fmean((r.get("num_turns") or 0) for r in rs),
            }
    return out


def analyze(runs: list[dict], base: str = "baseline", treat: str = "neuralmind") -> dict:
    tasks = per_task(runs)
    paired = {
        t: a
        for t, a in tasks.items()
        if base in a and treat in a and a[base]["cost"] is not None and a[treat]["cost"] is not None
    }
    diffs = [a[treat]["cost"] - a[base]["cost"] for a in paired.values()]
    rel = [
        (a[treat]["cost"] - a[base]["cost"]) / a[base]["cost"]
        for a in paired.values()
        if a[base]["cost"] > 0
    ]
    wil = wilcoxon_signed_rank(diffs)
    rel_median = statistics.median(rel) if rel else None
    rel_ci = bootstrap_ci(rel)

    solved_base = sum(a[base]["solved_majority"] for a in paired.values())
    solved_treat = sum(a[treat]["solved_majority"] for a in paired.values())
    only_base = sum(
        a[base]["solved_majority"] and not a[treat]["solved_majority"] for a in paired.values()
    )
    only_treat = sum(
        a[treat]["solved_majority"] and not a[base]["solved_majority"] for a in paired.values()
    )

    def cost_per_solved(arm: str) -> float | None:
        rs = [r for r in runs if r["arm"] == arm and r["task"] in paired]
        cost = sum(r.get("cost_usd") or 0 for r in rs)
        solved = sum(bool(r.get("solved")) for r in rs)
        return cost / solved if solved else None

    explore_diffs = [a[treat]["explore"] - a[base]["explore"] for a in paired.values()]
    cheaper = wil["p_less"] < ALPHA
    interval_below_zero = rel_ci[1] is not None and rel_ci[1] < 0
    not_worse = solved_treat >= solved_base - NONINFERIORITY_TASKS
    return {
        "tasks_paired": len(paired),
        "runs": len(runs),
        "cost": {
            "baseline_mean_per_task": (
                statistics.fmean(a[base]["cost"] for a in paired.values()) if paired else None
            ),
            "neuralmind_mean_per_task": (
                statistics.fmean(a[treat]["cost"] for a in paired.values()) if paired else None
            ),
            "median_relative_change": rel_median,
            "median_relative_change_ci95": rel_ci,
            "tasks_cheaper_with_neuralmind": sum(d < 0 for d in diffs),
            "tasks_dearer_with_neuralmind": sum(d > 0 for d in diffs),
            "wilcoxon": wil,
        },
        "solve": {
            "baseline_tasks_solved": solved_base,
            "neuralmind_tasks_solved": solved_treat,
            "only_baseline": only_base,
            "only_neuralmind": only_treat,
            "mcnemar_p": mcnemar_exact(only_base, only_treat),
        },
        "cost_per_solved_task": {base: cost_per_solved(base), treat: cost_per_solved(treat)},
        "exploration_calls_before_first_edit": {
            "median_change": statistics.median(explore_diffs) if explore_diffs else None,
            "wilcoxon": wilcoxon_signed_rank(explore_diffs),
        },
        "decision": {
            "cost_lower_p_lt_alpha": cheaper,
            "relative_change_ci_below_zero": interval_below_zero,
            "solve_rate_not_worse": not_worse,
            "claim_supported": cheaper and interval_below_zero and not_worse,
        },
    }


def _fmt_pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x * 100:+.1f}%"


def report(result: dict) -> str:
    c, s, d = result["cost"], result["solve"], result["decision"]
    lo, hi = c["median_relative_change_ci95"]
    cps = ", ".join(
        f"{arm} ${v:.3f}" if v is not None else f"{arm} n/a"
        for arm, v in result["cost_per_solved_task"].items()
    )
    lines = [
        f"Tasks paired: {result['tasks_paired']} ({result['runs']} runs)",
        (
            f"Median cost change per task with NeuralMind: {_fmt_pct(c['median_relative_change'])}"
            f" (95% CI {_fmt_pct(lo)} to {_fmt_pct(hi)})"
        ),
        (
            f"Cheaper on {c['tasks_cheaper_with_neuralmind']} task(s), dearer on"
            f" {c['tasks_dearer_with_neuralmind']};"
            f" Wilcoxon one-sided p = {c['wilcoxon']['p_less']:.4f}"
        ),
        (
            f"Tasks solved: baseline {s['baseline_tasks_solved']},"
            f" NeuralMind {s['neuralmind_tasks_solved']} (McNemar p = {s['mcnemar_p']:.4f})"
        ),
        f"Cost per solved task: {cps}",
        (
            f"Claim supported: {'YES' if d['claim_supported'] else 'NO'}"
            f" (p<{ALPHA}: {d['cost_lower_p_lt_alpha']},"
            f" CI below 0: {d['relative_change_ci_below_zero']},"
            f" solve rate not worse: {d['solve_rate_not_worse']})"
        ),
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("out_dir", type=Path)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    runs = [
        json.loads(line) for line in (args.out_dir / "runs.jsonl").read_text().splitlines() if line
    ]
    result = analyze(runs)
    print(json.dumps(result, indent=2) if args.json else report(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
