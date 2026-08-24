"""Tests for neuralmind.state_dir — the self-ignoring .neuralmind/ directory.

The guard exists because a user's repository has no .gitignore entry for
.neuralmind/, so a routine `git add -A` after a build would otherwise
commit cached command output. Stdlib-only.
"""

from __future__ import annotations

import subprocess

import pytest

from neuralmind.state_dir import (
    ensure_parent_dir,
    ensure_state_dir,
    state_dir,
    tracked_state_files,
)


def _git(*args, cwd):
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, check=False)


def _git_available() -> bool:
    try:
        return (
            subprocess.run(["git", "--version"], capture_output=True, check=False).returncode == 0
        )
    except (OSError, subprocess.SubprocessError):
        return False


requires_git = pytest.mark.skipif(not _git_available(), reason="git not installed")


class TestEnsureStateDir:
    def test_creates_directory(self, tmp_path):
        target = ensure_state_dir(tmp_path)
        assert target.is_dir()
        assert target == state_dir(tmp_path)

    def test_writes_self_ignoring_gitignore(self, tmp_path):
        guard = ensure_state_dir(tmp_path) / ".gitignore"
        assert guard.exists()
        # A bare `*` is what makes the directory ignore its own contents.
        assert "*" in guard.read_text().splitlines()

    def test_idempotent(self, tmp_path):
        ensure_state_dir(tmp_path)
        first = (state_dir(tmp_path) / ".gitignore").read_text()
        ensure_state_dir(tmp_path)
        assert (state_dir(tmp_path) / ".gitignore").read_text() == first

    def test_does_not_clobber_user_edits(self, tmp_path):
        guard = ensure_state_dir(tmp_path) / ".gitignore"
        guard.write_text("# my own rules\n*\n")
        ensure_state_dir(tmp_path)
        assert guard.read_text() == "# my own rules\n*\n"

    def test_survives_unwritable_parent(self, tmp_path):
        """A read-only checkout must degrade to 'no guard', never raise."""
        target = tmp_path / "ro"
        target.mkdir()
        target.chmod(0o500)
        try:
            ensure_state_dir(target)  # must not raise
        finally:
            target.chmod(0o700)


@requires_git
class TestGitBehaviour:
    def test_git_add_all_does_not_stage_state_dir(self, tmp_path):
        """The regression this whole guard exists to prevent."""
        _git("init", "-q", ".", cwd=tmp_path)
        _git("config", "user.email", "t@t.t", cwd=tmp_path)
        _git("config", "user.name", "t", cwd=tmp_path)
        (tmp_path / "app.py").write_text("print('hi')\n")

        nm = ensure_state_dir(tmp_path)
        (nm / "last_output.json").write_text('{"stdout": "ANTHROPIC_API_KEY=sk-ant-leaked"}')

        _git("add", "-A", cwd=tmp_path)
        staged = _git("diff", "--cached", "--name-only", cwd=tmp_path).stdout.split()
        assert staged == ["app.py"]
        assert not any(s.startswith(".neuralmind") for s in staged)

    def test_tracked_state_files_detects_prior_commit(self, tmp_path):
        """A project that committed .neuralmind/ before upgrading stays exposed."""
        _git("init", "-q", ".", cwd=tmp_path)
        _git("config", "user.email", "t@t.t", cwd=tmp_path)
        _git("config", "user.name", "t", cwd=tmp_path)

        nm = tmp_path / ".neuralmind"
        nm.mkdir()
        (nm / "last_output.json").write_text("{}")
        _git("add", "-f", ".neuralmind/last_output.json", cwd=tmp_path)
        _git("commit", "-qm", "oops", cwd=tmp_path)

        tracked = tracked_state_files(tmp_path)
        assert ".neuralmind/last_output.json" in tracked

    def test_tracked_state_files_empty_when_clean(self, tmp_path):
        _git("init", "-q", ".", cwd=tmp_path)
        ensure_state_dir(tmp_path)
        assert tracked_state_files(tmp_path) == []


def test_tracked_state_files_outside_a_repo(tmp_path):
    """Not a git repo — report nothing rather than raising."""
    assert tracked_state_files(tmp_path) == []


class TestEnsureParentDir:
    """Every flow that writes into .neuralmind/ must install the guard.

    The guard is only a guarantee if whichever flow creates the directory
    *first* installs it. Originally only `build` and the output-cache writer
    did, so a user whose first state-producing command was `ingest` — or a
    hook initialising the synapse store — got an unguarded directory that
    the next `git add -A` staged.
    """

    def test_creates_parent_and_guards_a_state_dir(self, tmp_path):
        target = tmp_path / ".neuralmind" / "synapses.db"
        ensure_parent_dir(target)
        assert target.parent.is_dir()
        assert (target.parent / ".gitignore").exists()

    def test_does_not_guard_an_ordinary_directory(self, tmp_path):
        """Only .neuralmind gets the marker — this is not a general policy."""
        target = tmp_path / "build" / "artifact.bin"
        ensure_parent_dir(target)
        assert target.parent.is_dir()
        assert not (target.parent / ".gitignore").exists()

    def test_idempotent_and_non_clobbering(self, tmp_path):
        target = tmp_path / ".neuralmind" / "a.json"
        ensure_parent_dir(target)
        guard = target.parent / ".gitignore"
        guard.write_text("# mine\n*\n")
        ensure_parent_dir(tmp_path / ".neuralmind" / "b.json")
        assert guard.read_text() == "# mine\n*\n"

    def test_survives_unwritable_parent(self, tmp_path):
        ro = tmp_path / "ro"
        ro.mkdir()
        ro.chmod(0o500)
        try:
            ensure_parent_dir(ro / ".neuralmind" / "x.json")  # must not raise
        finally:
            ro.chmod(0o700)


@requires_git
class TestGuardInstalledByNonBuildFlows:
    """The entry points that are not `build` must guard the directory too."""

    def _repo(self, tmp_path):
        _git("init", "-q", ".", cwd=tmp_path)
        _git("config", "user.email", "t@t.t", cwd=tmp_path)
        _git("config", "user.name", "t", cwd=tmp_path)
        (tmp_path / "app.py").write_text("print('hi')\n")
        return tmp_path

    def test_synapse_store_creating_the_dir_first(self, tmp_path):
        from neuralmind.synapses import SynapseStore

        repo = self._repo(tmp_path)
        SynapseStore(db_path=repo / ".neuralmind" / "synapses.db")

        assert (repo / ".neuralmind" / ".gitignore").exists()
        _git("add", "-A", cwd=repo)
        staged = _git("diff", "--cached", "--name-only", cwd=repo).stdout.split()
        assert staged == ["app.py"]

    def test_content_manifest_creating_the_dir_first(self, tmp_path):
        from neuralmind.content_manifest import ContentManifest

        repo = self._repo(tmp_path)
        ContentManifest(repo, {}).save()

        assert (repo / ".neuralmind" / ".gitignore").exists()
        _git("add", "-A", cwd=repo)
        staged = _git("diff", "--cached", "--name-only", cwd=repo).stdout.split()
        assert staged == ["app.py"]
