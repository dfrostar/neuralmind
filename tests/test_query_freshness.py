"""Query-time freshness notice (#631).

``query``, ``search`` and the MCP tools answer from a stale index without a
word. ``freshness.query_notice`` gives them one line instead: an index only in
the legacy layout, a failed background rebuild, or commits since the build
that changed the project. These tests use real git repositories; the hook
tests run the generated shell with a fake ``neuralmind``.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

import pytest

from neuralmind import freshness
from neuralmind.cli import _hook_rebuild_lines

_GIT_ENV = {
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.com",
}


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, env={**os.environ, **_GIT_ENV}
    )


def _commit(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    _git(root, "add", rel)
    _git(root, "commit", "-q", "-m", f"change {rel}")


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    _commit(root, "src/a.py", "def a():\n    return 1\n")
    return root


def _record_build(project: Path) -> None:
    """What a successful build leaves: when it started and the HEAD it saw.

    The reflog is aged so the commits before the build read as older than it
    whatever the filesystem's timestamp resolution.
    """
    root = project
    while not (root / ".git").exists():
        root = root.parent
    past = time.time() - 30
    os.utime(root / ".git" / "logs" / "HEAD", (past, past))
    state = project / ".neuralmind"
    state.mkdir(exist_ok=True)
    (state / "build_status.json").write_text(
        json.dumps(
            {"build_started_at": time.time() - 5, "build_head": freshness.head_commit(project)}
        ),
        encoding="utf-8",
    )


def test_a_fresh_build_carries_no_notice(tmp_path):
    root = _repo(tmp_path)
    _record_build(root)
    assert freshness.query_notice(root) == ""


def test_commits_since_the_build_that_change_the_project_are_named(tmp_path):
    root = _repo(tmp_path)
    _record_build(root)
    _commit(root, "src/a.py", "def a():\n    return 2\n")
    notice = freshness.query_notice(root)
    assert notice.startswith("Index is stale: 1 file changed in commits since the last build")
    assert "(src/a.py)" in notice
    assert f"run neuralmind build {root.resolve()}" in notice


def test_a_commit_elsewhere_in_the_repository_adds_nothing(tmp_path):
    root = _repo(tmp_path)
    _commit(root, "app/main.py", "x = 1\n")
    project = root / "app"
    _record_build(project)
    _commit(root, "other/b.py", "y = 2\n")  # moves HEAD, changes nothing in app/
    assert freshness.query_notice(project) == ""
    _commit(root, "app/main.py", "x = 2\n")
    assert "(main.py)" in freshness.query_notice(project)


def test_a_running_background_rebuild_says_so(tmp_path):
    root = _repo(tmp_path)
    _record_build(root)
    _commit(root, "src/a.py", "def a():\n    return 2\n")
    (root / ".neuralmind" / freshness.HOOK_BUILD_LOCK).mkdir()
    notice = freshness.query_notice(root)
    assert notice.startswith("Index is catching up:")
    assert "a background rebuild is running" in notice


def test_a_build_commit_that_is_gone_still_warns(tmp_path):
    root = _repo(tmp_path)
    _record_build(root)
    status_path = root / ".neuralmind" / "build_status.json"
    status = json.loads(status_path.read_text(encoding="utf-8"))
    status["build_head"] = "0" * 40  # rebased away
    status_path.write_text(json.dumps(status), encoding="utf-8")
    _commit(root, "src/a.py", "def a():\n    return 2\n")
    assert "HEAD moved to commits the index was not built from" in freshness.query_notice(root)


def test_a_failed_hook_rebuild_is_named_until_a_build_succeeds(tmp_path):
    root = _repo(tmp_path)
    _record_build(root)
    status_path = root / ".neuralmind" / "build_status.json"
    marker = root / ".neuralmind" / freshness.HOOK_BUILD_FAILED
    marker.touch()
    later = status_path.stat().st_mtime + 2
    os.utime(marker, (later, later))
    notice = freshness.query_notice(root)
    assert "the last background rebuild failed" in notice
    assert ".neuralmind/hook-build.log" in notice
    # A successful build after the failure rewrites build_status.json.
    newer = later + 2
    os.utime(status_path, (newer, newer))
    assert freshness.query_notice(root) == ""


def test_an_index_only_in_the_legacy_layout_is_named(tmp_path):
    root = _repo(tmp_path)
    assert freshness.query_notice(root) == ""  # never built: nothing to warn about
    (root / "graphify-out" / "neuralmind_db").mkdir(parents=True)
    notice = freshness.query_notice(root)
    assert "legacy graphify-out/ layout" in notice
    assert "semantic search finds nothing" in notice


def test_outside_git_and_on_bad_input_it_stays_quiet(tmp_path):
    project = tmp_path / "plain"
    (project / ".neuralmind").mkdir(parents=True)
    (project / ".neuralmind" / "build_status.json").write_text(
        json.dumps({"build_started_at": 1.0, "build_head": "abc"}), encoding="utf-8"
    )
    assert freshness.query_notice(project) == ""
    (project / ".neuralmind" / "build_status.json").write_text("{not json", encoding="utf-8")
    assert freshness.query_notice(project) == ""
    assert freshness.query_notice(tmp_path / "missing") == ""


def test_git_dir_follows_a_linked_worktree(tmp_path):
    root = _repo(tmp_path)
    linked = tmp_path / "linked"
    _git(root, "worktree", "add", "-q", str(linked))
    assert freshness.git_dir(root) == root / ".git"
    found = freshness.git_dir(linked)
    assert found is not None and found.parent.name == "worktrees"


# --------------------------------------------------------------------------- #
# The init-hook's rebuild leaves (and clears) the failure marker
# --------------------------------------------------------------------------- #
def _fake_build(tmp_path: Path, exit_code: int) -> Path:
    fake = tmp_path / "bin" / "neuralmind"
    fake.parent.mkdir(exist_ok=True)
    fake.write_text(f"#!/bin/sh\nexit {exit_code}\n", encoding="utf-8")
    fake.chmod(0o755)
    return fake


def _run_rebuild(project: Path, fake: Path, *, sync: bool) -> None:
    lines = _hook_rebuild_lines(f"'{project}'", sync=sync, announce=False)
    script = f"set -e\n_nm_bin='{fake}'\n{lines}"
    subprocess.run(["sh", "-c", script], check=True, capture_output=True, timeout=30)
    lock = project / ".neuralmind" / freshness.HOOK_BUILD_LOCK
    deadline = time.time() + 20
    while lock.exists() and time.time() < deadline:  # the background build
        time.sleep(0.05)


@pytest.mark.skipif(os.name == "nt", reason="POSIX shell hooks")
@pytest.mark.parametrize("sync", [True, False])
def test_the_hook_marks_a_failed_rebuild_and_clears_it_on_success(tmp_path, sync):
    project = tmp_path / "proj"
    (project / ".neuralmind").mkdir(parents=True)
    marker = project / ".neuralmind" / freshness.HOOK_BUILD_FAILED
    _run_rebuild(project, _fake_build(tmp_path, 1), sync=sync)
    assert marker.exists()
    _run_rebuild(project, _fake_build(tmp_path, 0), sync=sync)
    assert not marker.exists()


# --------------------------------------------------------------------------- #
# End to end: build, commit, query
# --------------------------------------------------------------------------- #
def test_query_and_mcp_carry_the_notice_after_a_commit(temp_project, monkeypatch):
    from neuralmind import NeuralMind, mcp_server

    _git(temp_project, "init", "-q")
    _commit(temp_project, "src/auth.py", "def login():\n    return True\n")
    mind = NeuralMind(str(temp_project))
    assert mind.build()["success"]
    status = json.loads((temp_project / ".neuralmind" / "build_status.json").read_text())
    assert status["build_head"] == freshness.head_commit(temp_project)
    assert isinstance(status["build_started_at"], float)

    assert mind.query("How does authentication work?").freshness == ""

    # A commit after the build: the reflog moves past the build's start.
    time.sleep(0.05)
    _commit(temp_project, "src/auth.py", "def login():\n    return False\n")
    logs = temp_project / ".git" / "logs" / "HEAD"
    future = status["build_started_at"] + 10
    os.utime(logs, (future, future))

    result = mind.query("How does authentication work?")
    assert result.freshness.startswith("Index is stale: 1 file changed")
    assert result.context.startswith(result.freshness + "\n\n")

    monkeypatch.setattr(mcp_server, "get_mind", lambda *a, **k: mind)
    payload = mcp_server.tool_query(str(temp_project), "How does authentication work?")
    assert payload["freshness"] == result.freshness
    hits = mcp_server.tool_search(str(temp_project), "authentication")
    assert hits
    assert hits[0]["freshness"] == result.freshness
    assert all("freshness" not in h for h in hits[1:])


def test_the_prompt_hook_block_carries_the_notice(temp_project, monkeypatch):
    # Claude Code and the Hermes plugin read recall from the prompt hook, not
    # from query(): the block must say when the index is stale too.
    from neuralmind import NeuralMind, hooks

    monkeypatch.setenv(hooks.RECALL_MIN_SIMILARITY_ENV, "0")
    _git(temp_project, "init", "-q")
    _commit(temp_project, "src/auth.py", "def login():\n    return True\n")
    assert NeuralMind(str(temp_project)).build()["success"]
    prompt = "How does authentication work?"
    block = hooks._spread_for_prompt(str(temp_project), prompt)
    assert block and "Index is stale" not in block

    _commit(temp_project, "src/auth.py", "def login():\n    return False\n")
    status = json.loads((temp_project / ".neuralmind" / "build_status.json").read_text())
    future = status["build_started_at"] + 10
    os.utime(temp_project / ".git" / "logs" / "HEAD", (future, future))
    block = hooks._spread_for_prompt(str(temp_project), prompt)
    assert block.rstrip().endswith("run neuralmind build " + str(temp_project.resolve()) + ".")
    assert "Index is stale: 1 file changed" in block
