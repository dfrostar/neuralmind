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

**Missing data, pre-registered.** A run that produced no final cost (it hit
the harness timeout) is scored unsolved at its budget cap, the worst case for
its arm, so a failure can never make an arm look cheaper. Any other gap fails
closed: every (task, arm) must hold the same seeds, or no verdict is given.

The claim "NeuralMind lowers the agent's cost per task without lowering its
solve rate" is made only when all three hold: the Wilcoxon p < 0.05, the
interval's upper bound is below zero, and NeuralMind solves no fewer tasks
than the baseline minus the pre-registered margin. Anything else is reported
as what it is: no effect shown, or a loss.

**The Hermes variant** (runs whose ``agent`` is ``hermes``, on a local model;
fixed in the spec's change log before its first run) has no cost to compare:

* **Primary, solve rate.** Solved per task as above; exact one-sided McNemar
  test on the discordant tasks. "With NeuralMind, the model solves more of
  these tasks" is supported only if p < 0.05.
* **Secondary, reported but not tested:** tokens (input plus output; median
  per-task relative change with its bootstrap interval), wall-clock minutes,
  turns, tool calls before the first edit, runs that edited a gold file, and
  solved runs per arm. A timed-out run is unsolved, with the tokens it used.
  Tokens and minutes cover the whole Hermes session, from the
  ``sessions.json`` that ``hermes_sessions`` writes beside ``runs.jsonl``;
  the report says how many runs lack one and fell back to their record.
* **Stage 1's stopping rule.** Over seed 0's runs, pooled across both arms:
  fewer than 5 solved means the tasks are too hard for this model to tell the
  arms apart, and stage 2 doesn't run.

**The memory track** (records with ``track`` ``memory``; fixed in the spec's
change log before its first run) compares ``carried`` runs, along chains that
carry NeuralMind's learned state from task to task, with ``fresh`` runs:

* **Primary, solve rate,** as for the Hermes variant: a task counts for a
  condition when most of its 3 runs solve it; exact one-sided McNemar test
  that carried solves more. Supported only if p < 0.05.
* **Mechanism, reported:** per condition, the tasks where most runs' blocks
  name a gold file, and where most put one first.
* **Prediction, reported as held or not:** carried solves at least as many of
  the 12 repeat tasks as fresh, and no more than one fewer of the other 8.
* **Also reported:** the Hermes variant's secondary endpoints, the carry-over
  check, and carried minus fresh solve share at each position.

Runs from different agents are never pooled: the analyzer refuses a mix.

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
STAGE1_SEED = 0
STAGE1_MIN_SOLVED_RUNS = 5  # Hermes variant: of stage 1's runs, pooled over both arms
BOOTSTRAP_SAMPLES = 10_000
BOOTSTRAP_SEED = 20261014
# Memory track: tasks with a gold file that a task earlier in the order also
# changed, from the spec's pre-registration.
MEMORY_REPEATS = frozenset(
    "8592aa7ab7 4325e063e1 4e01f40e6a e303c7a287 21bd34dfc4 108b1ee013 2a6448552b"
    " 24ee2924b9 b4c9886021 8c0411129c 454904f4bb fa72224183".split()
)


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


def mcnemar_exact_greater(only_baseline: int, only_neuralmind: int) -> float:
    """One-sided exact McNemar p-value that NeuralMind solves more tasks."""
    n = only_baseline + only_neuralmind
    if n == 0:
        return 1.0
    tail: float = sum(comb(n, i) for i in range(only_neuralmind, n + 1)) / 2**n
    return tail


def bootstrap_ci(values: list[float], stat=statistics.median, level: float = 0.95) -> tuple:
    if not values:
        return (None, None)
    rng = random.Random(BOOTSTRAP_SEED)
    samples = sorted(stat([rng.choice(values) for _ in values]) for _ in range(BOOTSTRAP_SAMPLES))
    lo = samples[int((1 - level) / 2 * BOOTSTRAP_SAMPLES)]
    hi = samples[int((1 + level) / 2 * BOOTSTRAP_SAMPLES) - 1]
    return (lo, hi)


class IncompleteRunsError(ValueError):
    """The run matrix has gaps; analysing it would weight the arms unequally."""


def run_cost(run: dict) -> float:
    """The run's reported cost, or its budget cap when it never reported one."""
    if run.get("cost_usd") is not None:
        return run["cost_usd"]
    if run.get("budget_usd") is None:
        raise IncompleteRunsError(
            f"{run['task']} {run['arm']} s{run.get('seed')}: no cost and no budget"
        )
    return run["budget_usd"]


def run_tokens(run: dict) -> int | None:
    """A Hermes run's tokens: input plus output, None when it recorded neither.

    The whole session's, when ``with_sessions`` attached them; else the
    record's, which cover the client's own turn (see ``hermes_sessions``).
    Never ``total_tokens``: Hermes reports 0 there for a session that ends in
    an error, though it records that session's input and output.
    """
    session = run.get("session")
    if session:
        return int(session["prompt_tokens"]) + int(session["output_tokens"])
    parts = [run.get("input_tokens"), run.get("output_tokens")]
    if all(x is None for x in parts):
        return None
    return sum(x or 0 for x in parts)


def run_minutes(run: dict) -> float | None:
    """The session's span when known, else the client's; None for neither."""
    session = run.get("session")
    if session and session.get("minutes") is not None:
        return float(session["minutes"])
    if run.get("duration_ms") is None:
        return None
    return float(run["duration_ms"]) / 60000


def with_sessions(runs: list[dict], sessions: dict[str, dict]) -> list[dict]:
    """Copies of ``runs`` with each one's whole-session usage under ``session``."""
    return [
        {**r, "session": sessions[r["session_id"]]} if r.get("session_id") in sessions else r
        for r in runs
    ]


def run_solved(run: dict) -> bool:
    return bool(run.get("solved")) and not run.get("timed_out")


def agent_of(runs: list[dict]) -> str:
    """The one agent these runs used (``claude`` for records that predate the field)."""
    agents = {r.get("agent", "claude") for r in runs}
    if len(agents) > 1:
        raise IncompleteRunsError(f"runs from more than one agent, never pooled: {sorted(agents)}")
    return agents.pop() if agents else "claude"


def check_complete(runs: list[dict], arms: tuple[str, ...]) -> None:
    """Every task has every arm, every (task, arm) the same seeds, none twice."""
    seen: dict[tuple[str, str], list] = {}
    for r in runs:
        seen.setdefault((r["task"], r["arm"]), []).append(r.get("seed"))
    seeds = {s for v in seen.values() for s in v}
    problems = []
    for task in sorted({t for t, _ in seen}):
        for arm in arms:
            got = seen.get((task, arm), [])
            if sorted(got) != sorted(seeds):
                problems.append(f"{task}/{arm}: seeds {sorted(got)}, expected {sorted(seeds)}")
    if problems:
        raise IncompleteRunsError("incomplete or duplicated runs: " + "; ".join(problems))


def per_task(runs: list[dict]) -> dict[str, dict[str, dict]]:
    """``{task: {arm: {cost, solved_share, solved_majority, explore, turns, n}}}``."""
    grouped: dict[str, dict[str, list[dict]]] = {}
    for r in runs:
        grouped.setdefault(r["task"], {}).setdefault(r["arm"], []).append(r)
    out: dict[str, dict[str, dict]] = {}
    for task, arms in grouped.items():
        out[task] = {}
        for arm, rs in arms.items():
            costs = [run_cost(r) for r in rs]
            solved = [bool(r.get("solved")) and not r.get("timed_out") for r in rs]
            out[task][arm] = {
                "n": len(rs),
                "cost": statistics.fmean(costs),
                "solved_share": sum(solved) / len(solved),
                "solved_majority": sum(solved) * 2 > len(solved),
                "explore": statistics.fmean(
                    r.get("explore_calls_before_first_edit", 0) for r in rs
                ),
                "turns": statistics.fmean((r.get("num_turns") or 0) for r in rs),
                "minutes": statistics.fmean((r.get("duration_ms") or 0) / 60000 for r in rs),
            }
    return out


def analyze(runs: list[dict], base: str = "baseline", treat: str = "neuralmind") -> dict:
    check_complete(runs, (base, treat))
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
        cost = sum(run_cost(r) for r in rs)
        solved = sum(bool(r.get("solved")) and not r.get("timed_out") for r in rs)
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
        "turns_per_task_median": {
            arm: statistics.median(a[arm]["turns"] for a in paired.values()) if paired else None
            for arm in (base, treat)
        },
        "minutes_per_task_median": {
            arm: statistics.median(a[arm]["minutes"] for a in paired.values()) if paired else None
            for arm in (base, treat)
        },
        "timed_out_runs": {
            arm: sum(bool(r.get("timed_out")) for r in runs if r["arm"] == arm)
            for arm in (base, treat)
        },
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


def stage_one(runs: list[dict]) -> dict:
    """The Hermes variant's stopping rule over seed 0's runs, both arms pooled."""
    first = [r for r in runs if r.get("seed") == STAGE1_SEED]
    solved = sum(run_solved(r) for r in first)
    return {
        "runs": len(first),
        "solved_runs": solved,
        "min_solved_runs": STAGE1_MIN_SOLVED_RUNS,
        "run_stage_two": solved >= STAGE1_MIN_SOLVED_RUNS,
    }


def analyze_hermes(runs: list[dict], base: str = "baseline", treat: str = "neuralmind") -> dict:
    """The Hermes variant's endpoints: solve rate primary, the rest reported only."""
    check_complete(runs, (base, treat))
    grouped: dict[str, dict[str, list[dict]]] = {}
    for r in runs:
        grouped.setdefault(r["task"], {}).setdefault(r["arm"], []).append(r)

    def majority(rs: list[dict]) -> bool:
        return sum(run_solved(r) for r in rs) * 2 > len(rs)

    def mean(values: list) -> float | None:
        values = [v for v in values if v is not None]
        return statistics.fmean(values) if values else None

    def median(values: list) -> float | None:
        values = [v for v in values if v is not None]
        return statistics.median(values) if values else None

    tasks = {t: a for t, a in grouped.items() if base in a and treat in a}
    only_base = sum(majority(a[base]) and not majority(a[treat]) for a in tasks.values())
    only_treat = sum(majority(a[treat]) and not majority(a[base]) for a in tasks.values())
    p = mcnemar_exact_greater(only_base, only_treat)

    per_task_tokens = {
        t: {arm: mean([run_tokens(r) for r in a[arm]]) for arm in (base, treat)}
        for t, a in tasks.items()
    }
    rel = []
    for v in per_task_tokens.values():
        b, n = v[base], v[treat]
        if b and n is not None:
            rel.append((n - b) / b)
    arm_runs = {
        arm: [r for r in runs if r["arm"] == arm and r["task"] in tasks] for arm in (base, treat)
    }
    return {
        "agent": "hermes",
        "tasks_paired": len(tasks),
        "runs": len(runs),
        "solve": {
            "baseline_tasks_solved": sum(majority(a[base]) for a in tasks.values()),
            "neuralmind_tasks_solved": sum(majority(a[treat]) for a in tasks.values()),
            "only_baseline": only_base,
            "only_neuralmind": only_treat,
            "mcnemar_p_greater": p,
            "solved_runs": {arm: sum(run_solved(r) for r in rs) for arm, rs in arm_runs.items()},
        },
        "tokens": {
            "median_per_task": {
                arm: median([v[arm] for v in per_task_tokens.values()]) for arm in (base, treat)
            },
            "median_relative_change": statistics.median(rel) if rel else None,
            "median_relative_change_ci95": bootstrap_ci(rel),
            "tasks_compared": len(rel),
            "runs_without_tokens": sorted(
                f"{r['task']} {r['arm']} s{r.get('seed')}" for r in runs if run_tokens(r) is None
            ),
        },
        "runs_without_session": sum(not r.get("session") for r in runs),
        "minutes_per_task_median": {
            arm: median([mean([run_minutes(r) for r in a[arm]]) for a in tasks.values()])
            for arm in (base, treat)
        },
        "turns_per_task_median": {
            arm: median([mean([r.get("num_turns") for r in a[arm]]) for a in tasks.values()])
            for arm in (base, treat)
        },
        "explore_calls_before_first_edit_median": {
            arm: median(
                [
                    mean([r.get("explore_calls_before_first_edit") for r in a[arm]])
                    for a in tasks.values()
                ]
            )
            for arm in (base, treat)
        },
        "gold_file_edited_runs": {
            arm: sum(bool(r.get("gold_touched")) for r in rs) for arm, rs in arm_runs.items()
        },
        "timed_out_runs": {
            arm: sum(bool(r.get("timed_out")) for r in rs) for arm, rs in arm_runs.items()
        },
        "stage_one": stage_one(runs),
        "decision": {"solves_more_p_lt_alpha": p < ALPHA, "claim_supported": p < ALPHA},
    }


def analyze_memory(runs: list[dict]) -> dict:
    """The memory track: carried against fresh, both in the ``neuralmind`` arm."""
    by_condition = [{**r, "arm": r["condition"]} for r in runs]
    base = analyze_hermes(by_condition, base="fresh", treat="carried")
    grouped: dict[str, dict[str, list[dict]]] = {}
    for r in by_condition:
        grouped.setdefault(r["task"], {}).setdefault(r["arm"], []).append(r)

    def most(rs: list[dict], key) -> bool:
        return sum(bool(key(r)) for r in rs) * 2 > len(rs)

    def solved_tasks(cond: str, tasks: set) -> int:
        return sum(most(grouped[t][cond], run_solved) for t in tasks if t in grouped)

    repeats = MEMORY_REPEATS & set(grouped)
    others = set(grouped) - MEMORY_REPEATS
    held_repeats = solved_tasks("carried", repeats) >= solved_tasks("fresh", repeats)
    held_others = solved_tasks("carried", others) >= solved_tasks("fresh", others) - 1
    positions: dict[int, dict[str, list[bool]]] = {}
    for r in by_condition:
        positions.setdefault(r.get("position"), {}).setdefault(r["arm"], []).append(run_solved(r))
    carried = [r for r in by_condition if r["arm"] == "carried"]
    later = [r for r in carried if (r.get("position") or 0) > 1]
    return {
        **base,
        "agent": "hermes",
        "track": "memory",
        "mechanism": {
            cond: {
                "tasks_block_names_gold": sum(
                    most(a[cond], lambda r: r.get("block_names_gold")) for a in grouped.values()
                ),
                "tasks_block_first_is_gold": sum(
                    most(a[cond], lambda r: r.get("block_first_is_gold")) for a in grouped.values()
                ),
                "runs_without_block": sum(
                    not r.get("block_sha256") for r in by_condition if r["arm"] == cond
                ),
            }
            for cond in ("fresh", "carried")
        },
        "prediction": {
            "repeats": {c: solved_tasks(c, repeats) for c in ("fresh", "carried")},
            "others": {c: solved_tasks(c, others) for c in ("fresh", "carried")},
            "repeat_tasks": len(repeats),
            "other_tasks": len(others),
            "held": held_repeats and held_others,
        },
        "carry_over": {
            "runs_after_the_first_position": len(later),
            "edges_in_median": (
                statistics.median(r.get("carry_edges_in", 0) for r in later) if later else None
            ),
            "edges_after_build_median": (
                statistics.median(r.get("carry_edges_after_build", 0) for r in later)
                if later
                else None
            ),
            "share_with_both_ends_in_graph": (
                sum(r.get("carry_edges_in_graph", 0) for r in later)
                / max(1, sum(r.get("carry_edges_after_build", 0) for r in later))
                if later
                else None
            ),
            "runs_starting_with_nothing_learned": sum(not r.get("carry_edges_in") for r in later),
            # Each run leaves one session recap, so a continuous chain's run at
            # position p starts with p - 1 of them.
            "runs_off_chain": sum(
                r.get("carry_recaps_in") != (r.get("position") or 1) - 1 for r in carried
            ),
        },
        "solve_share_by_position": {
            pos: (
                sum(v.get("carried", [])) / len(v["carried"]) if v.get("carried") else None,
                sum(v.get("fresh", [])) / len(v["fresh"]) if v.get("fresh") else None,
            )
            for pos, v in sorted(positions.items(), key=lambda kv: kv[0] or 0)
        },
    }


def report_memory(result: dict) -> str:
    s, t, m, p, c = (
        result["solve"],
        result["tokens"],
        result["mechanism"],
        result["prediction"],
        result["carry_over"],
    )
    lo, hi = t["median_relative_change_ci95"]
    share = c["share_with_both_ends_in_graph"]
    in_graph = "n/a" if share is None else f"{share:.0%}"

    def pair(d: dict, fmt: str = "{:.1f}") -> str:
        return ", ".join(f"{k} {'n/a' if v is None else fmt.format(v)}" for k, v in d.items())

    curve = " ".join(
        f"{pos}:{'n/a' if a is None or b is None else f'{a - b:+.2f}'}"
        for pos, (a, b) in result["solve_share_by_position"].items()
    )
    lines = [
        (
            f"Agent: Hermes, memory track. Tasks paired: {result['tasks_paired']}"
            f" ({result['runs']} runs)"
        ),
        (
            f"Tasks solved: fresh {s['baseline_tasks_solved']},"
            f" carried {s['neuralmind_tasks_solved']}; only fresh {s['only_baseline']},"
            f" only carried {s['only_neuralmind']}"
            f" (one-sided McNemar p = {s['mcnemar_p_greater']:.4f})"
        ),
        "Solved runs: " + pair(s["solved_runs"], "{}"),
        "Mechanism, reported:",
        "  Tasks where most blocks name a gold file: "
        + pair({k: v["tasks_block_names_gold"] for k, v in m.items()}, "{}"),
        "  Tasks where most blocks name a gold file first: "
        + pair({k: v["tasks_block_first_is_gold"] for k, v in m.items()}, "{}"),
        "  Runs with no block read back: "
        + pair({k: v["runs_without_block"] for k, v in m.items()}, "{}"),
        (
            f"Prediction ({p['repeat_tasks']} repeat tasks, {p['other_tasks']} others):"
            f" repeats solved {pair(p['repeats'], '{}')}; others {pair(p['others'], '{}')};"
            f" {'held' if p['held'] else 'not held'}"
        ),
        (
            f"Carry-over, {c['runs_after_the_first_position']} carried runs after position 1:"
            f" median learned edges in {c['edges_in_median']}, after the build"
            f" {c['edges_after_build_median']}; share with both ends in the graph"
            f" {in_graph};"
            f" starting with nothing learned {c['runs_starting_with_nothing_learned']};"
            f" off their chain (recaps in other than position - 1) {c['runs_off_chain']}"
        ),
        "Carried minus fresh solve share by position: " + curve,
        "Secondary, not tested:",
        (
            f"  Median tokens per task: {pair(t['median_per_task'], '{:,.0f}')};"
            f" median change carried {_fmt_pct(t['median_relative_change'])}"
            f" (95% CI {_fmt_pct(lo)} to {_fmt_pct(hi)}, {t['tasks_compared']} tasks)"
        ),
        "  Median minutes per task: " + pair(result["minutes_per_task_median"]),
        "  Median turns per task: " + pair(result["turns_per_task_median"]),
        "  Median tool calls before the first edit: "
        + pair(result["explore_calls_before_first_edit_median"]),
        "  Runs that edited a gold file: " + pair(result["gold_file_edited_runs"], "{}"),
        "  Runs that hit the timeout (unsolved): " + pair(result["timed_out_runs"], "{}"),
    ]
    if result["runs_without_session"]:
        lines.append(
            f"  {result['runs_without_session']} of {result['runs']} runs have no session"
            " usage: their tokens and minutes cover the client's own turn only"
        )
    lines.append(
        f"Claim supported: {'YES' if result['decision']['claim_supported'] else 'NO'}"
        f" (more tasks solved with carried state, p<{ALPHA})"
    )
    return "\n".join(lines)


def report_hermes(result: dict) -> str:
    s, t, st = result["solve"], result["tokens"], result["stage_one"]
    lo, hi = t["median_relative_change_ci95"]

    def pair(d: dict, fmt: str = "{:.1f}") -> str:
        return ", ".join(f"{k} {'n/a' if v is None else fmt.format(v)}" for k, v in d.items())

    lines = [
        f"Agent: Hermes. Tasks paired: {result['tasks_paired']} ({result['runs']} runs)",
        (
            f"Tasks solved: baseline {s['baseline_tasks_solved']},"
            f" NeuralMind {s['neuralmind_tasks_solved']}; only baseline {s['only_baseline']},"
            f" only NeuralMind {s['only_neuralmind']}"
            f" (one-sided McNemar p = {s['mcnemar_p_greater']:.4f})"
        ),
        "Solved runs: " + pair(s["solved_runs"], "{}"),
        (
            f"Stage 1 (seed {STAGE1_SEED}, both arms): {st['solved_runs']} of {st['runs']} runs"
            f" solved; stage 2 runs at {st['min_solved_runs']} or more:"
            f" {'yes' if st['run_stage_two'] else 'no'}"
        ),
        "Secondary, not tested:",
        (
            f"  Median tokens per task: {pair(t['median_per_task'], '{:,.0f}')};"
            f" median change with NeuralMind {_fmt_pct(t['median_relative_change'])}"
            f" (95% CI {_fmt_pct(lo)} to {_fmt_pct(hi)}, {t['tasks_compared']} tasks)"
        ),
        "  Median minutes per task: " + pair(result["minutes_per_task_median"]),
        "  Median turns per task: " + pair(result["turns_per_task_median"]),
        "  Median tool calls before the first edit: "
        + pair(result["explore_calls_before_first_edit_median"]),
        "  Runs that edited a gold file: " + pair(result["gold_file_edited_runs"], "{}"),
        "  Runs that hit the timeout (unsolved): " + pair(result["timed_out_runs"], "{}"),
    ]
    if result["runs_without_session"]:
        lines.append(
            f"  {result['runs_without_session']} of {result['runs']} runs have no session"
            " usage (no sessions.json, or not in it): their tokens and minutes cover the"
            " client's own turn only"
        )
    if t["runs_without_tokens"]:
        lines.append("  Runs with no tokens recorded: " + ", ".join(t["runs_without_tokens"]))
    lines.append(
        f"Claim supported: {'YES' if result['decision']['claim_supported'] else 'NO'}"
        f" (more tasks solved with NeuralMind, p<{ALPHA})"
    )
    return "\n".join(lines)


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
            "Median turns per task: "
            + ", ".join(
                f"{k} {v:.1f}" for k, v in result["turns_per_task_median"].items() if v is not None
            )
            + "; median minutes per task: "
            + ", ".join(
                f"{k} {v:.1f}"
                for k, v in result["minutes_per_task_median"].items()
                if v is not None
            )
        ),
        "Runs that hit the timeout (scored unsolved at the budget cap): "
        + ", ".join(f"{k} {v}" for k, v in result["timed_out_runs"].items()),
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
    tracks = {r.get("track", "task") for r in runs}
    try:
        if len(tracks) > 1:
            raise IncompleteRunsError(f"runs from more than one track: {sorted(tracks)}")
        hermes = agent_of(runs) == "hermes"
        memory = tracks == {"memory"}
        if hermes:
            sessions_file = args.out_dir / "sessions.json"
            if sessions_file.is_file():
                runs = with_sessions(runs, json.loads(sessions_file.read_text()))
        if memory:
            result = analyze_memory(runs)
        else:
            result = analyze_hermes(runs) if hermes else analyze(runs)
    except IncompleteRunsError as exc:
        print(f"no verdict: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, indent=2))
    elif memory:
        print(report_memory(result))
    else:
        print(report_hermes(result) if hermes else report(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
