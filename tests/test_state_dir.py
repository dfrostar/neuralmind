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


class TestGuardWriteIsConstrained:
    """The guard write is pinned to one filename in one directory name.

    The directory reaching `_install_guard` derives from a caller-supplied
    project path — a CLI argument, or an MCP tool input an agent chose — so
    the sink is constrained rather than trusting the caller. CodeQL flags
    this flow (argv -> path -> write); the invariant is what makes it safe,
    and these tests are what keep it true.
    """

    def test_guard_is_never_written_outside_a_state_dir(self, tmp_path):
        from neuralmind.state_dir import _install_guard

        for name in ["src", "docs", ".git", "neuralmind", ".neuralmind-backup"]:
            d = tmp_path / name
            d.mkdir()
            _install_guard(d)
            assert not (d / ".gitignore").exists(), f"wrote a guard into {name}/"

    def test_guard_is_written_into_a_state_dir(self, tmp_path):
        from neuralmind.state_dir import _install_guard

        d = tmp_path / ".neuralmind"
        d.mkdir()
        _install_guard(d)
        assert (d / ".gitignore").exists()

    def test_missing_directory_is_not_created_by_the_guard(self, tmp_path):
        """_install_guard writes; it does not create. Must not raise either."""
        from neuralmind.state_dir import _install_guard

        _install_guard(tmp_path / ".neuralmind")
        assert not (tmp_path / ".neuralmind").exists()

    def test_dotdot_in_the_path_cannot_escape(self, tmp_path):
        """A `..` segment resolves before use rather than walking out."""
        nested = tmp_path / "a" / "b"
        nested.mkdir(parents=True)
        target = nested / ".." / ".." / ".neuralmind" / "synapses.db"
        parent = ensure_parent_dir(target)

        assert parent == (tmp_path / ".neuralmind").resolve()
        assert (parent / ".gitignore").exists()
        # nothing was created under the nested path
        assert not (nested / ".neuralmind").exists()

    def test_only_gitignore_is_ever_written(self, tmp_path):
        """The state dir gains exactly one file from the guard."""
        d = ensure_state_dir(tmp_path)
        assert sorted(x.name for x in d.iterdir()) == [".gitignore"]


class TestExistingGuardIsValidated:
    """An existing .gitignore is not proof of protection.

    The idempotency rule ("don't clobber user edits") quietly became
    "accept no protection at all" when the file was empty or narrowly
    scoped, while this function still reported success.
    """

    def _guard(self, tmp_path):
        return state_dir(tmp_path) / ".gitignore"

    def test_empty_guard_gains_the_catch_all(self, tmp_path):
        state_dir(tmp_path).mkdir(parents=True)
        self._guard(tmp_path).write_text("")
        ensure_state_dir(tmp_path)
        assert "*" in self._guard(tmp_path).read_text().split()

    def test_narrow_guard_keeps_user_rules_and_gains_the_catch_all(self, tmp_path):
        state_dir(tmp_path).mkdir(parents=True)
        self._guard(tmp_path).write_text("# my rules\n*.tmp\n")
        ensure_state_dir(tmp_path)
        text = self._guard(tmp_path).read_text()
        assert "*.tmp" in text, "user rules were discarded"
        assert "# my rules" in text
        assert any(line.strip() == "*" for line in text.splitlines())

    def test_effective_guard_is_left_alone(self, tmp_path):
        state_dir(tmp_path).mkdir(parents=True)
        self._guard(tmp_path).write_text("# mine\n*\n")
        ensure_state_dir(tmp_path)
        assert self._guard(tmp_path).read_text() == "# mine\n*\n"

    def test_repeated_calls_do_not_stack_rules(self, tmp_path):
        state_dir(tmp_path).mkdir(parents=True)
        self._guard(tmp_path).write_text("*.tmp\n")
        for _ in range(3):
            ensure_state_dir(tmp_path)
        text = self._guard(tmp_path).read_text()
        assert [line.strip() for line in text.splitlines()].count("*") == 1


@requires_git
class TestNarrowGuardActuallyProtects:
    """End-to-end: the repaired guard has to stop a real `git add -A`."""

    def test_repaired_guard_blocks_staging(self, tmp_path):
        _git("init", "-q", ".", cwd=tmp_path)
        _git("config", "user.email", "t@t.t", cwd=tmp_path)
        _git("config", "user.name", "t", cwd=tmp_path)
        (tmp_path / "app.py").write_text("print('hi')\n")

        nm = state_dir(tmp_path)
        nm.mkdir(parents=True)
        (nm / ".gitignore").write_text("*.tmp\n")  # narrow: does not protect
        (nm / "last_output.json").write_text('{"stdout": "secret"}')

        ensure_state_dir(tmp_path)
        _git("add", "-A", cwd=tmp_path)
        staged = _git("diff", "--cached", "--name-only", cwd=tmp_path).stdout.split()
        assert staged == ["app.py"]
