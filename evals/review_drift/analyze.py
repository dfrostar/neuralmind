"""Apply the spec's endpoints and decision rule to a results directory.

    python -m evals.review_drift.analyze bench/review_drift/<date>

Reads ``records.jsonl``, writes ``summary.json`` beside it and prints the
tables as Markdown. The thresholds are the pre-registered ones in
``docs/specs/REVIEW-DRIFT-EVAL-SPEC.md``; change them there first.
"""

from __future__ import annotations

import collections
import json
import statistics
import sys
from fractions import Fraction
from pathlib import Path

REVIEW_HIT10_FLOOR = 0.50
REVIEW_MARGIN_OVER_COCHANGE = 0.05
DRIFT_RECALL_FLOOR = 0.15
DRIFT_RATIO_OVER_CONTROL = 2.0
METHODS = ("review", "cochange", "adjacency")


CUTOFF = 10  # review lists at most ten entries; every method is scored to the same depth


def hits_at(ranks: list[int | None], k: int) -> int:
    return sum(1 for r in ranks if r is not None and r <= k)


def hit_at(ranks: list[int | None], k: int) -> float:
    return hits_at(ranks, k) / len(ranks) if ranks else 0.0


def mrr(ranks: list[int | None], k: int = CUTOFF) -> float:
    """Mean reciprocal rank, with ranks beyond ``k`` scored as misses.

    ``review`` returns at most ``k`` entries, so a baseline's rank 30 must
    count for as little as review's miss does, or the baselines get credit
    review cannot.
    """
    return sum(1 / r for r in ranks if r is not None and r <= k) / len(ranks) if ranks else 0.0


def expected_random(pairs: list[dict], k: int) -> float:
    """Expected hit@k of a uniform draw among the candidates, averaged over pairs."""
    vals = [min(1.0, k / p["n_candidates"]) for p in pairs if p.get("n_candidates")]
    return statistics.fmean(vals) if vals else 0.0


def review_table(pairs: list[dict]) -> dict:
    out: dict = {"pairs": len(pairs)}
    for m in METHODS:
        ranks = [p[f"rank_{m}"] for p in pairs]
        out[m] = {
            "hits@5": hits_at(ranks, 5),
            "hits@10": hits_at(ranks, 10),
            "hit@5": round(hit_at(ranks, 5), 3),
            "hit@10": round(hit_at(ranks, 10), 3),
            "mrr@10": round(mrr(ranks), 3),
        }
    out["random"] = {
        "hit@5": round(expected_random(pairs, 5), 3),
        "hit@10": round(expected_random(pairs, 10), 3),
    }
    by_commit: dict[str, list[dict]] = collections.defaultdict(list)
    for p in pairs:
        by_commit[p["commit"]].append(p)
    out["commits"] = len(by_commit)
    out["commits_with_a_hit@10"] = (
        round(
            sum(
                1
                for ps in by_commit.values()
                if any(p["rank_review"] is not None and p["rank_review"] <= 10 for p in ps)
            )
            / len(by_commit),
            3,
        )
        if by_commit
        else 0.0
    )
    lengths = [len(p["review_list"]) for p in pairs]
    entries = sum(lengths)
    out["list_length_median"] = statistics.median(lengths) if lengths else 0
    out["lists_shorter_than_10"] = (
        round(sum(1 for n in lengths if n < 10) / len(lengths), 3) if lengths else 0.0
    )
    out["lists_empty"] = sum(1 for n in lengths if n == 0)
    out["test_entry_share"] = (
        round(sum(p["test_entries"] for p in pairs) / entries, 3) if entries else 0.0
    )
    out["held_out_is_test_share"] = (
        round(sum(1 for p in pairs if _is_test(p["held_out"])) / len(pairs), 3) if pairs else 0.0
    )
    times = [p["elapsed_s"] for p in pairs]
    out["review_call_median_s"] = round(statistics.median(times), 2) if times else None
    return out


def _is_test(path: str) -> bool:
    from evals.review_drift.select import is_test_path

    return is_test_path(path)


def drift_table(records: list[dict]) -> dict:
    out: dict = {}
    for which in ("fix", "control"):
        rs = [r for r in records if r["set"] == which]
        hits = [r for r in rs if r["n_findings"] > 0]
        # A commit that only added lines leaves drift nothing to examine on
        # the parent's side. It counts as a miss in `rate` and is reported on
        # its own; `rate_examinable` is the hit rate over the rest.
        examinable = [r for r in rs if r.get("changed_files")]
        out[which] = {
            "commits": len(rs),
            "with_a_finding": len(hits),
            "rate": round(len(hits) / len(rs), 3) if rs else None,
            "no_examinable_lines": len(rs) - len(examinable),
            "rate_examinable": (round(len(hits) / len(examinable), 3) if examinable else None),
            "findings_per_commit": (
                round(statistics.fmean(r["n_findings"] for r in rs), 3) if rs else None
            ),
            "symbols_checked_median": (
                statistics.median([r["symbols_checked"] or 0 for r in rs]) if rs else None
            ),
            "graph_missing": sum(1 for r in examinable if r.get("graph") == "missing"),
        }
    return out


def decide(review: dict, drift: dict) -> dict:
    """The spec's rule, evaluated on exact counts.

    Rates in the tables are rounded for reading; a gate must not pass on a
    rounding (500 of 1001 is not 0.50) or fail on floating-point addition
    (0.55 + 0.05 is not 0.60 in binary), so each comparison is rewritten as
    an integer inequality.
    """
    verdict: dict = {}
    n = review.get("pairs")
    if n:
        hr, hc = review["review"]["hits@10"], review["cochange"]["hits@10"]
        # Fraction(str(x)) is the decimal the spec wrote, not its binary float.
        floor_num, floor_den = Fraction(str(REVIEW_HIT10_FLOOR)).as_integer_ratio()
        margin_num, margin_den = Fraction(str(REVIEW_MARGIN_OVER_COCHANGE)).as_integer_ratio()
        verdict["review"] = {
            "hit@10": review["review"]["hit@10"],
            "cochange_hit@10": review["cochange"]["hit@10"],
            "hits@10": hr,
            "cochange_hits@10": hc,
            "pairs": n,
            # hr / n >= floor  <=>  hr * floor_den >= floor_num * n
            "floor_met": hr * floor_den >= floor_num * n,
            # (hr - hc) / n >= margin  <=>  (hr - hc) * margin_den >= margin_num * n
            "beats_cochange": (hr - hc) * margin_den >= margin_num * n,
        }
        verdict["review"]["worth_quoting"] = (
            verdict["review"]["floor_met"] and verdict["review"]["beats_cochange"]
        )
    fix, ctl = drift.get("fix", {}), drift.get("control", {})
    if fix.get("commits"):
        fh, fn = fix["with_a_finding"], fix["commits"]
        ch, cn = ctl.get("with_a_finding"), ctl.get("commits")
        floor_num, floor_den = Fraction(str(DRIFT_RECALL_FLOOR)).as_integer_ratio()
        verdict["drift"] = {
            "recall_fix": fix["rate"],
            "rate_control": ctl.get("rate"),
            "fix_hits": fh,
            "fix_commits": fn,
            "control_hits": ch,
            "control_commits": cn,
            "floor_met": fh * floor_den >= floor_num * fn,
            # fh / fn >= ratio * ch / cn  <=>  fh * cn >= ratio * ch * fn
            "beats_control": (fh * cn >= DRIFT_RATIO_OVER_CONTROL * ch * fn) if cn else None,
        }
        verdict["drift"]["worth_quoting"] = bool(
            verdict["drift"]["floor_met"] and verdict["drift"]["beats_control"]
        )
    return verdict


def load(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in (path / "records.jsonl").read_text().splitlines()
        if line.strip()
    ]


def markdown(summary: dict) -> str:
    lines = []
    rv = summary["review"]
    if rv.get("pooled", {}).get("pairs"):
        lines.append("### Review: the held-out file's rank\n")
        lines.append(
            "| Set | Pairs | Method | hit@5 | hit@10 | MRR@10 |\n|---|---|---|---|---|---|"
        )
        for name, t in [("pooled", rv["pooled"]), *sorted(rv["per_repo"].items())]:
            for m in METHODS:
                lines.append(
                    f"| {name} | {t['pairs']} | {m} | {t[m]['hit@5']:.3f} | {t[m]['hit@10']:.3f} | {t[m]['mrr@10']:.3f} |"
                )
            lines.append(
                f"| {name} | {t['pairs']} | random (expected) | {t['random']['hit@5']:.3f} | {t['random']['hit@10']:.3f} | — |"
            )
        p = rv["pooled"]
        lines.append(
            f"\nCommits {p['commits']}; review named at least one missing file (top 10) on {p['commits_with_a_hit@10']:.0%}; "
            f"list length median {p['list_length_median']}, shorter than 10 on {p['lists_shorter_than_10']:.0%}, empty {p['lists_empty']}; "
            f"test files were {p['test_entry_share']:.0%} of list entries and {p['held_out_is_test_share']:.0%} of held-out files; "
            f"median review call {p['review_call_median_s']} s. Dropped commits (ground truth < 2 indexed files): {rv['dropped_commits']}.\n"
        )
    dr = summary["drift"]
    if dr.get("pooled", {}).get("fix", {}).get("commits"):
        lines.append("### Drift: commits with at least one finding\n")
        lines.append(
            "| Set | Fix commits | with a finding | rate | Control commits | with a finding | rate | findings/commit (fix, control) |\n|---|---|---|---|---|---|---|---|"
        )
        for name, t in [("pooled (public)", dr["pooled"]), *sorted(dr["per_repo"].items())]:
            f, c = t["fix"], t.get("control", {})
            lines.append(
                f"| {name} | {f['commits']} | {f['with_a_finding']} | {f['rate']} | {c.get('commits', 0)} | {c.get('with_a_finding', 0)} | {c.get('rate')} | {f['findings_per_commit']}, {c.get('findings_per_commit')} |"
            )
    lines.append("\n### Decision rule\n")
    lines.append("```json\n" + json.dumps(summary["verdict"], indent=1) + "\n```")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print(__doc__)
        return 2
    path = Path(argv[0])
    records = load(path)
    pairs = [r for r in records if r["kind"] == "review_pair"]
    commits = [r for r in records if r["kind"] == "review_commit"]
    drift = [r for r in records if r["kind"] == "drift"]
    public_drift = [r for r in drift if r["repo"] != "hermes-agent"]
    hermes_drift = [r for r in drift if r["repo"] == "hermes-agent"]
    repos = sorted({r["repo"] for r in pairs} | {r["repo"] for r in drift})
    summary = {
        "spec": "docs/specs/REVIEW-DRIFT-EVAL-SPEC.md",
        "tool": next((r["tool"] for r in records if r["kind"] == "run_start"), None),
        "builds": {
            "count": sum(1 for r in records if r["kind"] == "build"),
            "failed": sum(1 for r in records if r["kind"] == "build" and not r["ok"]),
            "median_s": (
                statistics.median([r["elapsed_s"] for r in records if r["kind"] == "build"])
                if any(r["kind"] == "build" for r in records)
                else None
            ),
            "synapse_namespaces_seen": sorted(
                {
                    ns
                    for r in records
                    if r["kind"] == "build"
                    for ns in r.get("synapse_namespaces", {})
                }
            ),
        },
        "review": {
            "pooled": review_table(pairs),
            "per_repo": {
                name: review_table([p for p in pairs if p["repo"] == name])
                for name in repos
                if any(p["repo"] == name for p in pairs)
            },
            "dropped_commits": sum(1 for c in commits if c["dropped"]),
            "errors": sum(1 for p in pairs if p.get("error")),
        },
        "drift": {
            "pooled": drift_table(public_drift),
            "per_repo": {
                name: drift_table([r for r in public_drift if r["repo"] == name])
                for name in repos
                if any(r["repo"] == name for r in public_drift)
            },
            "hermes_agent": drift_table(hermes_drift) if hermes_drift else None,
            "errors": sum(1 for r in drift if r.get("error")),
        },
    }
    summary["verdict"] = decide(summary["review"]["pooled"], summary["drift"]["pooled"])
    (path / "summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    print(markdown(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
