"""The review/drift eval's selection rules, baselines and metrics (stdlib only).

The commands under test run as subprocesses in the real harness; these tests
cover the parts around them, which decide what the spec's numbers mean.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from evals.review_drift import analyze, run, select


def test_is_test_path_matches_the_usual_layouts():
    assert select.is_test_path("tests/test_x.py")
    assert select.is_test_path("src/pkg/tests/helpers.py")
    assert select.is_test_path("pkg/test_y.py")
    assert select.is_test_path("pkg/y_test.py")
    assert not select.is_test_path("src/pkg/testing.py")
    assert not select.is_test_path("src/pkg/contest.py")


def test_select_sets_applies_the_file_counts_and_subject_rule():
    commits = [
        {
            "commit": "a",
            "parent": "a0",
            "subject": "fix: two files",
            "files": ["src/p/a.py", "src/p/b.py", "tests/test_a.py"],
        },
        {"commit": "b", "parent": "b0", "subject": "add feature", "files": ["src/p/c.py"]},
        {"commit": "c", "parent": "c0", "subject": "docs", "files": ["README.md"]},
        {
            "commit": "d",
            "parent": "d0",
            "subject": "refactor everything",
            "files": [f"src/p/f{i}.py" for i in range(7)],
        },
        {
            "commit": "e",
            "parent": "e0",
            "subject": "Fix a regression",
            "files": ["src/p/d.py", "src/p/e.py"],
        },
        {"commit": "f", "parent": "f0", "subject": "tests only", "files": ["tests/test_b.py"]},
    ]
    sets = select.select_sets(commits, "src/p", cap=40)
    assert [c["commit"] for c in sets["review"]] == ["a", "e"]
    assert [c["commit"] for c in sets["fix"]] == ["a", "e"]
    # as many controls as fixes, most recent first, non-matching subjects only
    assert [c["commit"] for c in sets["control"]] == ["b"]
    assert sets["review"][0]["source_files"] == ["src/p/a.py", "src/p/b.py"]


def test_select_cap_limits_each_set():
    commits = [
        {"commit": str(i), "parent": "p", "subject": "fix", "files": ["src/p/a.py", "src/p/b.py"]}
        for i in range(5)
    ]
    sets = select.select_sets(commits, "src/p", cap=2)
    assert len(sets["review"]) == 2 and len(sets["fix"]) == 2


def test_rank_of_is_one_based_and_none_on_miss():
    assert run.rank_of("b", ["a", "b"]) == 2
    assert run.rank_of("z", ["a", "b"]) is None


def test_metrics():
    ranks = [1, 3, None, 12]
    assert analyze.hit_at(ranks, 5) == 0.5
    assert analyze.hit_at(ranks, 10) == 0.5
    # rank 12 is beyond the ten-entry cutoff every method is scored to
    assert analyze.mrr(ranks) == pytest.approx((1 + 1 / 3 + 0 + 0) / 4)
    assert analyze.mrr(ranks, k=12) == pytest.approx((1 + 1 / 3 + 0 + 1 / 12) / 4)
    pairs = [{"n_candidates": 40}, {"n_candidates": 5}]
    assert analyze.expected_random(pairs, 10) == pytest.approx((0.25 + 1.0) / 2)


def test_decision_rule_uses_the_spec_thresholds():
    def rv(hr, hc, n):
        return {
            "pairs": n,
            "review": {"hits@10": hr, "hit@10": round(hr / n, 3)},
            "cochange": {"hits@10": hc, "hit@10": round(hc / n, 3)},
        }

    def dr(fh, fn, ch, cn):
        return {
            "fix": {"commits": fn, "with_a_finding": fh, "rate": round(fh / fn, 3)},
            "control": {"commits": cn, "with_a_finding": ch, "rate": round(ch / cn, 3)},
        }

    v = analyze.decide(rv(60, 50, 100), dr(3, 10, 1, 10))
    assert v["review"]["worth_quoting"] is True
    assert v["drift"]["worth_quoting"] is True
    v = analyze.decide(rv(54, 50, 100), dr(2, 10, 15, 100))
    assert v["review"]["worth_quoting"] is False  # margin under 5 points
    assert v["drift"]["worth_quoting"] is False  # under twice the control rate
    # Exact counts, not rounded rates: 500 of 1001 is below the 0.50 floor,
    # and 60 of 100 against 55 of 100 is exactly the 5-point margin.
    assert analyze.decide(rv(500, 0, 1001), {})["review"]["floor_met"] is False
    assert analyze.decide(rv(60, 55, 100), {})["review"]["beats_cochange"] is True


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout


def _commit(repo: Path, files: dict[str, str], message: str) -> str:
    for name, text in files.items():
        p = repo / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    _git(repo, "add", "-A")
    _git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", message)
    return _git(repo, "rev-parse", "HEAD").strip()


def test_cochange_ranking_counts_commits_touching_a_seed(tmp_path):
    repo = tmp_path
    _git(repo, "init", "-q")
    _commit(repo, {"a.py": "1", "b.py": "1", "c.py": "1", "d.py": "1"}, "base")
    _commit(repo, {"a.py": "2", "b.py": "2"}, "a+b")
    _commit(repo, {"a.py": "3", "b.py": "3"}, "a+b again")
    _commit(repo, {"a.py": "4", "c.py": "4"}, "a+c")
    _commit(repo, {"d.py": "4", "e.py": "1"}, "d+e, no a")
    head = _commit(repo, {"a.py": "5"}, "the commit under study")
    # The window is the commits before `head`'s parent... counting from the
    # commit passed as `parent`, so pass `head`. In it, a co-changed with b in
    # three commits (base, a+b, a+b again), with c in two (base, a+c), with d in
    # one (base) and with e never.
    ranking = run.cochange_ranking(repo, head, {"a.py"}, {"b.py", "c.py", "d.py", "e.py"})
    assert ranking == ["b.py", "c.py", "d.py"]
    assert run.rank_of("e.py", ranking) is None


def test_modified_files_excludes_added_and_deleted(tmp_path):
    repo = tmp_path
    _git(repo, "init", "-q")
    p = _commit(repo, {"keep.py": "1", "gone.py": "1"}, "base")
    (repo / "gone.py").unlink()
    c = _commit(repo, {"keep.py": "2", "new.py": "1"}, "change")
    assert run.modified_files(repo, p, c) == ["keep.py"]


def test_adjacency_ranking_counts_cross_file_edges(tmp_path):
    import sqlite3

    nm = tmp_path / ".neuralmind"
    nm.mkdir()
    conn = sqlite3.connect(str(nm / "synapses.db"))
    conn.execute(
        "create table structural_edges (caller text, callee text, call_count int, edge_type text, last_seen real)"
    )
    rows = [
        ("a_f", "b_g", 1, "call", 0.0),
        ("a_f", "b_h", 1, "call", 0.0),
        ("c_x", "a_f", 1, "import", 0.0),
        ("a", "a_f", 1, "contains", 0.0),  # hierarchy, not adjacency
        ("a_f", "a_g", 1, "call", 0.0),  # same file
    ]
    conn.executemany("insert into structural_edges values (?,?,?,?,?)", rows)
    conn.commit()
    conn.close()
    node_file = {
        "a_f": "a.py",
        "a_g": "a.py",
        "b_g": "b.py",
        "b_h": "b.py",
        "c_x": "c.py",
        "a": "a.py",
    }
    ranking = run.adjacency_ranking(tmp_path, node_file, {"a.py"}, {"b.py", "c.py", "d.py"})
    assert ranking == ["b.py", "c.py"]


def test_review_table_and_markdown_render(tmp_path):
    pairs = [
        {
            "repo": "r",
            "commit": "c1",
            "held_out": "x.py",
            "n_candidates": 20,
            "review_list": ["x.py", "tests/test_x.py"],
            "rank_review": 1,
            "rank_cochange": None,
            "rank_adjacency": 2,
            "test_entries": 1,
            "elapsed_s": 0.5,
        },
        {
            "repo": "r",
            "commit": "c1",
            "held_out": "tests/test_x.py",
            "n_candidates": 20,
            "review_list": [],
            "rank_review": None,
            "rank_cochange": 1,
            "rank_adjacency": None,
            "test_entries": 0,
            "elapsed_s": 0.4,
        },
    ]
    t = analyze.review_table(pairs)
    assert t["review"]["hit@10"] == 0.5 and t["cochange"]["hit@10"] == 0.5
    assert t["lists_empty"] == 1 and t["test_entry_share"] == 0.5
    (tmp_path / "records.jsonl").write_text(
        "\n".join(
            json.dumps(r)
            for r in [
                {"kind": "run_start", "tool": {"version": "x"}},
                {
                    "kind": "build",
                    "repo": "r",
                    "parent": "p",
                    "ok": True,
                    "elapsed_s": 1.0,
                    "synapse_namespaces": {"shared": 3},
                },
                {"kind": "review_commit", "repo": "r", "commit": "c1", "dropped": False},
                *[{"kind": "review_pair", **p} for p in pairs],
                {
                    "kind": "drift",
                    "repo": "r",
                    "set": "fix",
                    "n_findings": 1,
                    "symbols_checked": 2,
                    "graph": "loaded",
                },
                {
                    "kind": "drift",
                    "repo": "r",
                    "set": "control",
                    "n_findings": 0,
                    "symbols_checked": 1,
                    "graph": "loaded",
                },
            ]
        )
    )
    assert analyze.main([str(tmp_path)]) == 0
    summary = json.loads((tmp_path / "summary.json").read_text())
    assert summary["verdict"]["review"]["worth_quoting"] is False
    assert summary["drift"]["pooled"]["fix"]["rate"] == 1.0


def test_cochange_ties_break_on_the_path(tmp_path):
    repo = tmp_path
    _git(repo, "init", "-q")
    _commit(repo, {"a.py": "1", "z.py": "1", "m.py": "1"}, "base")
    head = _commit(repo, {"a.py": "2"}, "study")
    # z and m tie on count and recency; the path decides, every run.
    assert run.cochange_ranking(repo, head, {"a.py"}, {"z.py", "m.py"}) == ["m.py", "z.py"]


def test_prune_incomplete_drops_an_unfinished_parent(tmp_path):
    path = tmp_path / "records.jsonl"
    rows = [
        {"kind": "run_start", "tool": {}},
        {"kind": "build", "repo": "r", "parent": "p1", "ok": True},
        {"kind": "review_pair", "repo": "r", "parent": "p1", "held_out": "x"},
        {"kind": "parent_done", "repo": "r", "parent": "p1"},
        {"kind": "build", "repo": "r", "parent": "p2", "ok": True},
        {"kind": "review_pair", "repo": "r", "parent": "p2", "held_out": "y"},
    ]
    run.write_records(path, rows)
    assert run.prune_incomplete(path) == 2
    kept = run.load_records(path)
    assert [r["kind"] for r in kept] == ["run_start", "build", "review_pair", "parent_done"]
    assert run.done_parents(path) == {("r", "p1")}
    assert run.prune_incomplete(path) == 0
