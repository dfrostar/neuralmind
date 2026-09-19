"""Integration tests — TRD 10.2 (full lifecycle, export/import roundtrip, concurrency)."""

from __future__ import annotations

import json
import subprocess
import threading

import pytest

from neuralmind.memory.invalidate import InvalidationEngine
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
    _git(repo, "config", "user.email", "t@t.com")
    _git(repo, "config", "user.name", "T")
    (repo / "mod.py").write_text("a = 1\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "init")
    return repo


def test_full_lifecycle_record_query_invalidate_audit(git_repo):
    store = DecisionStore(str(git_repo))
    sha = subprocess.run(
        ["git", "-C", str(git_repo), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    # Record
    rec = store.record(
        title="Lifecycle decision",
        rationale="Full lifecycle test rationale with keywords.",
        commit_sha=sha,
        files_affected=["mod.py"],
    )

    # Query — must surface
    assert any(d.id == rec.id for d in store.query("lifecycle keywords"))

    # Invalidate via engine (commit a change)
    (git_repo / "mod.py").write_text("a = 2\n")
    _git(git_repo, "add", "-A")
    _git(git_repo, "commit", "-qm", "change")
    engine = InvalidationEngine(str(git_repo), store)
    invalidated = engine.scan()
    assert rec.id in invalidated

    # Query — stale filtered out by default
    assert store.query("lifecycle keywords") == []

    # Audit — invalidated decision visible via list_all
    assert rec.id in {d.id for d in store.list_all()}


def test_export_import_roundtrip(tmp_path):
    store = DecisionStore(str(tmp_path))
    original = store.record(
        title="Roundtrip",
        rationale="Lossless serialization check.",
        commit_sha="d" * 40,
        files_affected=["x.py", "y.py"],
        tags=["rt"],
        evidence=["e1"],
        rejected_alternatives=["alt1"],
    )
    payload = json.loads(store.export(format="json"))

    # Import into a second store
    other_dir = tmp_path / "imported"
    other_dir.mkdir()
    other = DecisionStore(str(other_dir))
    for d in payload:
        other.record(
            title=d["title"],
            rationale=d["rationale"],
            commit_sha=d["commit_sha"],
            files_affected=d.get("files_affected", []),
            tags=d.get("tags", []),
            evidence=d.get("evidence", []),
            rejected_alternatives=d.get("rejected_alternatives", []),
            id=d["id"],
        )
    got = other.get(original.id)
    assert got is not None
    assert got.title == original.title
    assert got.files_affected == original.files_affected
    assert got.tags == original.tags
    assert got.evidence == original.evidence
    assert got.rejected_alternatives == original.rejected_alternatives


def test_concurrent_reads_and_writes(tmp_path):
    """TRD 10.2: 10 agents querying + writing concurrently, no crashes."""
    store = DecisionStore(str(tmp_path))
    store.record(title="seed", rationale="seed rationale", commit_sha="e" * 40)
    errors = []

    def writer(n):
        try:
            for i in range(5):
                store.record(
                    title=f"writer {n} item {i}",
                    rationale="concurrent write",
                    commit_sha="f" * 40,
                )
        except Exception as e:  # pragma: no cover
            errors.append(e)

    def reader(n):
        try:
            for _ in range(10):
                store.query("seed rationale")
        except Exception as e:  # pragma: no cover
            errors.append(e)

    threads = [threading.Thread(target=writer, args=(n,)) for n in range(4)] + [
        threading.Thread(target=reader, args=(n,)) for n in range(6)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert errors == [], f"concurrent access raised: {errors}"
    assert len(store.list_all()) >= 21  # 1 seed + 4*5 writes


def test_git_hook_failure_degrades_gracefully(tmp_path):
    """TRD 10.4: broken git repo must not raise from the engine."""
    bad = tmp_path / "badrepo"
    bad.mkdir()
    (bad / ".git").mkdir()  # fake .git, no actual repo
    store = DecisionStore(str(bad))
    store.record(title="x", rationale="y", commit_sha="0" * 40)
    engine = InvalidationEngine(str(bad), store)
    assert engine.scan() == []  # graceful, no exception
