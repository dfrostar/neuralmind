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
