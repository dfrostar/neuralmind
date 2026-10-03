"""Unit tests for InvalidationEngine — TRD 10.1 (file change detection, commit invalidation)."""

from __future__ import annotations

import subprocess

import pytest

from neuralmind.memory.invalidate import (
    InMemoryDecisionStore,
    InvalidationEngine,
    get_changed_files,
    get_current_commit,
    is_file_changed,
    is_git_repo,
)
from neuralmind.memory.store import DecisionStore


def _git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


@pytest.fixture
def git_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "src.py").write_text("x = 1\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "initial")
    return repo


@pytest.fixture
def store(tmp_path):
    return DecisionStore(str(tmp_path))


def _commit_change(repo, filename="src.py", content="x = 2\n"):
    (repo / filename).write_text(content)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "change")


# ------------------------------------------------------------------ #
# Git helpers
# ------------------------------------------------------------------ #


def test_is_git_repo_true(git_repo):
    assert is_git_repo(git_repo)


def test_is_git_repo_false(tmp_path):
    assert not is_git_repo(tmp_path)


def test_get_current_commit(git_repo):
    sha = get_current_commit(git_repo)
    assert len(sha) >= 7


def test_get_changed_files(git_repo):
    _commit_change(git_repo, "new.py")
    changed = get_changed_files(git_repo)
    assert any("new.py" in f for f in changed)


def test_is_file_changed(git_repo):
    old_sha = get_current_commit(git_repo)
    _commit_change(git_repo)
    assert is_file_changed("src.py", old_sha, git_repo)


# ------------------------------------------------------------------ #
# Engine
# ------------------------------------------------------------------ #


def test_scan_noop_when_not_git_repo(tmp_path, store):
    engine = InvalidationEngine(str(tmp_path), store)
    assert engine.scan() == []


def test_scan_invalidates_on_file_touch(git_repo, store):
    store.record(
        title="Decision about src.py",
        rationale="reasons",
        commit_sha=get_current_commit(git_repo),
        files_affected=["src.py"],
    )
    _commit_change(git_repo)
    engine = InvalidationEngine(str(git_repo), store)
    invalidated = engine.scan()
    assert len(invalidated) == 1
    assert store.get(invalidated[0]).status == "STALE"


def test_scan_idempotent(git_repo, store):
    store.record(
        title="Decision about src.py",
        rationale="reasons",
        commit_sha=get_current_commit(git_repo),
        files_affected=["src.py"],
    )
    _commit_change(git_repo)
    engine = InvalidationEngine(str(git_repo), store)
    first = engine.scan()
    second = engine.scan()
    assert first != []
    assert second == [], "already-stale decisions must not be re-invalidated"


def test_scan_untouched_files_not_invalidated(git_repo, store):
    store.record(
        title="Decision about other.py",
        rationale="reasons",
        commit_sha=get_current_commit(git_repo),
        files_affected=["other.py"],
    )
    _commit_change(git_repo)
    engine = InvalidationEngine(str(git_repo), store)
    assert engine.scan() == []


def test_scan_skips_when_no_changes(git_repo, store):
    # HEAD commit has changes vs its parent, but a fresh clone-like state:
    # record decision at HEAD, no further commits -> changed files exist but
    # decision matches HEAD. Commit-mismatch path is the conservative guard.
    sha = get_current_commit(git_repo)
    store.record(
        title="Decision at HEAD",
        rationale="reasons",
        commit_sha=sha,
        files_affected=["src.py"],
    )
    engine = InvalidationEngine(str(git_repo), store)
    # files changed in HEAD commit + decision anchored at HEAD -> no mismatch
    invalidated = engine.scan()
    assert invalidated == []


def test_scan_commit_mismatch_invalidates(git_repo, store):
    """Commit-mismatch is a secondary guard: a decision whose files changed
    AND whose anchor commit differs from HEAD is invalidated with a
    commit_mismatch reason. Untouched files are never invalidated even on
    commit mismatch (conservative file-based scoping)."""
    old_sha = get_current_commit(git_repo)
    store.record(
        title="Decision anchored to old commit",
        rationale="reasons",
        commit_sha=old_sha,
        files_affected=["src.py"],
    )
    _commit_change(git_repo)
    engine = InvalidationEngine(str(git_repo), store)
    invalidated = engine.scan()
    assert len(invalidated) == 1


def test_scan_no_invalidations_for_untouched_files_on_commit_mismatch(git_repo, store):
    old_sha = get_current_commit(git_repo)
    store.record(
        title="Decision about untouched file",
        rationale="reasons",
        commit_sha=old_sha,
        files_affected=["unrelated.py"],
    )
    _commit_change(git_repo)
    engine = InvalidationEngine(str(git_repo), store)
    assert engine.scan() == []


def test_scan_cascades_to_dependents(git_repo, store):
    base = store.record(
        title="Base decision",
        rationale="reasons",
        commit_sha=get_current_commit(git_repo),
        files_affected=["src.py"],
    )
    store.record(
        title="Dependent decision",
        rationale="depends on base",
        commit_sha=get_current_commit(git_repo),
        files_affected=["other.py"],
        dependency_constraints=[base.id],
    )
    _commit_change(git_repo)
    engine = InvalidationEngine(str(git_repo), store)
    invalidated = engine.scan()
    assert len(invalidated) == 2, "cascade must invalidate the dependent too"
    statuses = {store.get(i).status for i in invalidated}
    assert statuses == {"STALE"}


# ------------------------------------------------------------------ #
# InMemoryDecisionStore (protocol impl used by the engine)
# ------------------------------------------------------------------ #


def test_in_memory_store_records_and_finds():
    from neuralmind.memory.store import DecisionRecord

    mem = InMemoryDecisionStore()
    rec = DecisionRecord(
        title="t",
        rationale="r",
        commit_sha="a" * 40,
        files_affected=["f.py"],
    )
    mem.add(rec)
    assert [d.id for d in mem.find_by_files(["f.py"])] == [rec.id]


def test_in_memory_store_finds_dependents():
    from neuralmind.memory.store import DecisionRecord

    mem = InMemoryDecisionStore()
    base = DecisionRecord(
        title="base",
        rationale="r",
        commit_sha="a" * 40,
        files_affected=["b.py"],
    )
    dep = DecisionRecord(
        title="dep",
        rationale="r",
        commit_sha="a" * 40,
        files_affected=["d.py"],
        dependency_constraints=[base.id],
    )
    mem.add(base)
    mem.add(dep)
    assert [d.id for d in mem.find_dependents(base.id)] == [dep.id]


# ------------------------------------------------------------------ #
# Post-commit semantics (wired in via `neuralmind decisions scan`)
# ------------------------------------------------------------------ #


def _backdate(path, seconds=120):
    """Make a file look as if it was last edited ``seconds`` ago."""
    import os
    import time

    then = time.time() - seconds
    os.utime(path, (then, then))


def test_commit_carrying_the_decision_keeps_it_active(git_repo, store):
    """Edit, record why, commit: the commit that lands the change keeps it.

    The decision was recorded after the file's last edit, so it already
    describes what this commit contains.
    """
    (git_repo / "src.py").write_text("x = 22\n")  # new size: git can't miss it
    _backdate(git_repo / "src.py")
    rec = store.record(
        title="Bump x",
        rationale="x must be 2 for the new protocol",
        commit_sha=get_current_commit(git_repo),  # CLI default: the parent
        files_affected=["src.py"],
    )
    _git(git_repo, "commit", "-qam", "bump x")
    assert InvalidationEngine(str(git_repo), store).scan() == []
    assert store.get(rec.id).status == "ACTIVE"


def test_edit_after_recording_goes_stale_in_the_next_commit(git_repo, store):
    (git_repo / "src.py").write_text("x = 22\n")  # new size: git can't miss it
    _backdate(git_repo / "src.py")
    rec = store.record(
        title="Bump x",
        rationale="x must be 2",
        commit_sha=get_current_commit(git_repo),
        files_affected=["src.py"],
    )
    _git(git_repo, "commit", "-qam", "bump x")
    assert InvalidationEngine(str(git_repo), store).scan() == []
    # A later edit the decision never saw:
    _commit_change(git_repo, "src.py", "x = 3\n")
    assert InvalidationEngine(str(git_repo), store).scan() == [rec.id]
    assert store.get(rec.id).status == "STALE"


def test_decision_without_commit_anchor_goes_stale(git_repo, store):
    """MCP-recorded decisions often carry no commit SHA."""
    rec = store.record(title="t", rationale="r", commit_sha="", files_affected=["src.py"])
    _commit_change(git_repo)
    assert InvalidationEngine(str(git_repo), store).scan() == [rec.id]


def test_decision_anchored_at_head_is_left_alone(git_repo, store):
    from datetime import datetime, timedelta, timezone

    _commit_change(git_repo)
    rec = store.record(
        title="Made at HEAD",
        rationale="r",
        commit_sha=get_current_commit(git_repo),
        files_affected=["src.py"],
        # Older than the edit, so only the HEAD anchor keeps it ACTIVE.
        updated_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    assert InvalidationEngine(str(git_repo), store).scan() == []
    assert store.get(rec.id).status == "ACTIVE"


def test_reason_is_recorded_on_the_decision(git_repo, store):
    rec = store.record(title="t", rationale="r", commit_sha="abc", files_affected=["src.py"])
    _commit_change(git_repo)
    engine = InvalidationEngine(str(git_repo), store)
    engine.scan()
    head = get_current_commit(git_repo)
    note = store.get(rec.id).evidence[-1]
    assert (
        note == f"Marked STALE: commit {head[:7]} changed src.py after this decision was recorded"
    )
    assert engine.last_events[0].files == ["src.py"]
    assert engine.last_events[0].commit_sha == head


def test_absolute_paths_in_decisions_match(git_repo, store):
    rec = store.record(
        title="t", rationale="r", commit_sha="abc", files_affected=[str(git_repo / "src.py")]
    )
    _commit_change(git_repo)
    assert InvalidationEngine(str(git_repo), store).scan() == [rec.id]


def test_deleted_file_goes_stale(git_repo, store):
    rec = store.record(title="t", rationale="r", commit_sha="abc", files_affected=["src.py"])
    _git(git_repo, "rm", "-q", "src.py")
    _git(git_repo, "commit", "-qm", "remove src")
    assert InvalidationEngine(str(git_repo), store).scan() == [rec.id]


def test_rename_counts_the_old_path(git_repo, store):
    rec = store.record(title="t", rationale="r", commit_sha="abc", files_affected=["src.py"])
    _git(git_repo, "mv", "src.py", "renamed.py")
    _git(git_repo, "commit", "-qm", "rename")
    assert InvalidationEngine(str(git_repo), store).scan() == [rec.id]


def test_merge_commit_counts_what_it_brought_in(git_repo, store):
    base = _git(git_repo, "rev-parse", "--abbrev-ref", "HEAD")
    _git(git_repo, "checkout", "-qb", "feature")
    _commit_change(git_repo, "src.py", "x = 9\n")
    _git(git_repo, "checkout", "-q", base)
    (git_repo / "other.py").write_text("y = 1\n")
    _git(git_repo, "add", "-A")
    _git(git_repo, "commit", "-qm", "unrelated")
    rec = store.record(title="t", rationale="r", commit_sha="abc", files_affected=["src.py"])
    _git(git_repo, "merge", "-q", "--no-ff", "--no-edit", "feature")
    assert InvalidationEngine(str(git_repo), store).scan() == [rec.id]


def test_project_in_a_subdirectory_uses_its_own_relative_paths(git_repo):
    project = git_repo / "pkg"
    project.mkdir()
    (project / "mod.py").write_text("a = 1\n")
    (git_repo / "README.md").write_text("readme\n")
    _git(git_repo, "add", "-A")
    _git(git_repo, "commit", "-qm", "add pkg")
    store = DecisionStore(str(project))
    rec = store.record(title="t", rationale="r", commit_sha="abc", files_affected=["mod.py"])
    unrelated = store.record(
        title="u", rationale="r", commit_sha="abc", files_affected=["README.md"]
    )
    (project / "mod.py").write_text("a = 2\n")
    (git_repo / "README.md").write_text("changed\n")
    _git(git_repo, "commit", "-qam", "change both")
    assert get_changed_files(project) == ["mod.py"]
    assert InvalidationEngine(str(project), store).scan() == [rec.id]
    assert store.get(unrelated.id).status == "ACTIVE"


def test_event_bus_failure_does_not_break_the_scan(git_repo, store, monkeypatch):
    import neuralmind.event_bus as event_bus

    def _boom(*_a, **_k):
        raise RuntimeError("bus down")

    monkeypatch.setattr(event_bus, "publish", _boom)
    rec = store.record(title="t", rationale="r", commit_sha="abc", files_affected=["src.py"])
    _commit_change(git_repo)
    assert InvalidationEngine(str(git_repo), store).scan() == [rec.id]


def test_store_without_mark_stale_uses_update_status(git_repo):
    from neuralmind.memory.store import DecisionRecord

    mem = InMemoryDecisionStore()
    rec = DecisionRecord(title="t", rationale="r", commit_sha="abc", files_affected=["src.py"])
    mem.add(rec)
    _commit_change(git_repo)
    assert InvalidationEngine(str(git_repo), mem).scan() == [rec.id]
    assert mem.find_stale()[0].id == rec.id


def test_root_commit_lists_its_files(tmp_path):
    repo = tmp_path / "fresh"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "a.py").write_text("a = 1\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "root")
    assert get_changed_files(repo) == ["a.py"]
