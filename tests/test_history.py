"""Tests for git-history co-change mining (neuralmind/history.py).

Stdlib-only: the parser is tested against hand-written git-log output and the
edge builder against synthetic commit filesets, so nothing here needs a git
binary or a real repository. The namespace-wiring tests use a real
SynapseStore on a temp sqlite file.
"""

from __future__ import annotations

from neuralmind import history
from neuralmind.synapses import (
    HISTORY_NAMESPACE,
    LTP_THRESHOLD,
    W_HISTORY,
    W_PERSONAL,
    W_SHARED,
    WEIGHT_CAP,
    SynapseStore,
    merge_weight_for,
)

# NUL delimiter that prefixes each commit's hash line in our git-log format.
NUL = "\x00"


def _log(*commits: list[str]) -> list[str]:
    """Build git-log output lines from (hash, *paths) commit tuples.

    Each commit renders as a NUL-prefixed hash line, then one line per path,
    then a blank line — exactly what `git log --name-only --pretty=format:%x00%H`
    emits.
    """
    lines: list[str] = []
    for i, paths in enumerate(commits):
        lines.append(f"{NUL}{'0' * 39}{i}")
        lines.extend(paths)
        lines.append("")
    return lines


# --------------------------------------------------------------------------- #
# build_file_node_index
# --------------------------------------------------------------------------- #


def test_file_node_index_picks_file_nodes_not_symbols():
    nodes = [
        {"id": "api_py", "label": "api.py", "source_file": "api.py"},
        {"id": "api_py__handler_fn", "label": "handler()", "source_file": "api.py"},
        {"id": "models_py", "label": "models.py", "source_file": "models.py"},
    ]
    index = history.build_file_node_index(nodes)
    assert index == {"api.py": "api_py", "models.py": "models_py"}


def test_file_node_index_skips_files_with_no_file_node():
    # Only symbol nodes for a path -> that path is absent, never guessed.
    nodes = [{"id": "x_py__f_fn", "label": "f()", "source_file": "x.py"}]
    assert history.build_file_node_index(nodes) == {}


# --------------------------------------------------------------------------- #
# parse_git_log
# --------------------------------------------------------------------------- #


def test_parse_splits_commits_on_nul_sentinel():
    lines = _log(["a.py", "b.py"], ["c.py"])
    assert list(history.parse_git_log(lines)) == [["a.py", "b.py"], ["c.py"]]


def test_parse_handles_empty_commit():
    lines = _log(["a.py"], [], ["b.py"])
    assert list(history.parse_git_log(lines)) == [["a.py"], [], ["b.py"]]


def test_parse_tolerates_output_before_first_sentinel():
    # No crash if something precedes the first commit marker.
    lines = ["stray line", *_log(["a.py"])]
    assert list(history.parse_git_log(lines)) == [["a.py"]]


def test_parse_caps_pathological_commit_at_hard_limit():
    huge = [f"f{i}.py" for i in range(history._HARD_FILE_LIMIT + 100)]
    (result,) = list(history.parse_git_log(_log(huge)))
    assert len(result) == history._HARD_FILE_LIMIT


# --------------------------------------------------------------------------- #
# cochange_edges — weighting, gates, stats
# --------------------------------------------------------------------------- #

IDX = {p: p for p in ("a", "b", "c", "d", "e")}  # identity path->node for tests


def test_two_file_commit_makes_one_edge_at_base_weight():
    rows, stats = history.cochange_edges([["a", "b"]], IDX)
    assert len(rows) == 1
    a, b, weight, count = rows[0]
    assert {a, b} == {"a", "b"}
    assert abs(weight - history.PAIR_WEIGHT_BASE) < 1e-9  # k=2 -> base/(k-1)=base
    assert count == 1
    assert stats["commits_used"] == 1
    assert stats["edges"] == 1


def test_larger_commits_contribute_less_per_pair():
    # Same pair (a,b) in a focused 2-file commit vs a 5-file commit.
    focused, _ = history.cochange_edges([["a", "b"]], IDX)
    broad, _ = history.cochange_edges([["a", "b", "c", "d", "e"]], IDX)
    ab_focused = focused[0][2]
    ab_broad = next(w for x, y, w, _ in broad if {x, y} == {"a", "b"})
    assert ab_broad < ab_focused
    assert abs(ab_broad - history.PAIR_WEIGHT_BASE / 4) < 1e-9  # base/(k-1), k=5


def test_repeated_cochange_accumulates_and_saturates_at_cap():
    commits = [["a", "b"]] * 10  # base=0.5 each -> 5.0, saturates
    rows, _ = history.cochange_edges(commits, IDX)
    (a, b, weight, count) = rows[0]
    assert weight == WEIGHT_CAP
    assert count == 10


def test_pair_seen_enough_times_is_marked_durable():
    commits = [["a", "b"]] * LTP_THRESHOLD
    rows, stats = history.cochange_edges(commits, IDX)
    assert rows[0][3] == LTP_THRESHOLD
    assert stats["ltp_edges"] == 1

    fewer, stats2 = history.cochange_edges([["a", "b"]] * (LTP_THRESHOLD - 1), IDX)
    assert stats2["ltp_edges"] == 0


def test_oversized_commits_are_skipped():
    rows, stats = history.cochange_edges([["a", "b", "c", "d", "e"]], IDX, max_files=3)
    assert rows == []
    assert stats["commits_too_large"] == 1
    assert stats["commits_used"] == 0


def test_paths_not_in_index_are_dropped():
    # 'ghost' was renamed away / never indexed; only a,b map to nodes.
    rows, stats = history.cochange_edges([["a", "ghost", "b"]], IDX)
    assert len(rows) == 1
    assert {rows[0][0], rows[0][1]} == {"a", "b"}


def test_single_indexable_file_yields_no_edge():
    rows, stats = history.cochange_edges([["a", "ghost"]], IDX)
    assert rows == []
    assert stats["commits_no_overlap"] == 1


def test_duplicate_paths_in_one_commit_are_deduped():
    rows, _ = history.cochange_edges([["a", "a", "b"]], IDX)
    assert len(rows) == 1


# --------------------------------------------------------------------------- #
# Namespace wiring — the mined edges must reach a merged read
# --------------------------------------------------------------------------- #


def test_history_namespace_read_weight_is_below_personal_and_shared():
    # A mined prior is the quietest signal in a merged read.
    w = merge_weight_for(HISTORY_NAMESPACE, active_namespace="personal")
    assert w == W_HISTORY
    assert W_HISTORY < W_SHARED < W_PERSONAL


def test_imported_history_edges_surface_in_merged_read(tmp_path):
    store = SynapseStore(tmp_path / "synapses.db")
    # (node_a, node_b, weight, activation_count) — import_edges contract.
    store.import_edges(
        [("api_py", "models_py", WEIGHT_CAP, LTP_THRESHOLD)],
        namespace=HISTORY_NAMESPACE,
    )
    # No personal usage at all — this is the cold-start scenario.
    assert store.neighbors("api_py", namespaces=["personal"]) == []

    # The default merged read still surfaces the mined association, scaled
    # by W_HISTORY.
    merged = dict(store.neighbors("api_py"))
    assert "models_py" in merged
    assert abs(merged["models_py"] - W_HISTORY * WEIGHT_CAP) < 1e-9


def test_history_edges_are_isolated_and_independently_clearable(tmp_path):
    store = SynapseStore(tmp_path / "synapses.db")
    store.reinforce(["x", "y"])  # real usage in personal
    store.import_edges([("api_py", "models_py", 0.8, 3)], namespace=HISTORY_NAMESPACE)

    store.clear_namespace(HISTORY_NAMESPACE)
    assert store.neighbors("api_py", namespaces=[HISTORY_NAMESPACE]) == []
    # Personal usage is untouched.
    assert "y" in dict(store.neighbors("x", namespaces=["personal"]))


# --------------------------------------------------------------------------- #
# run_git_log — the one path the pure tests can't reach
# --------------------------------------------------------------------------- #


def _git(cwd, *args):
    import subprocess

    subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def test_run_git_log_round_trips_real_history(tmp_path):
    import shutil

    import pytest

    if shutil.which("git") is None:
        pytest.skip("git not installed")

    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "t@t.co")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "a.py").write_text("x = 1\n")
    (tmp_path / "b.py").write_text("y = 1\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-m", "both", "--no-gpg-sign")

    lines = history.run_git_log(tmp_path, max_commits=10)
    commits = list(history.parse_git_log(lines))
    assert len(commits) == 1
    assert sorted(commits[0]) == ["a.py", "b.py"]


def test_run_git_log_is_empty_outside_a_repo(tmp_path):
    # A non-repo directory yields no lines, so mining reports "no commits"
    # rather than raising.
    assert list(history.run_git_log(tmp_path, max_commits=10)) == []
