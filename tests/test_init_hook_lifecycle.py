"""init-hook lifecycle hardening (#630).

More triggers (post-merge / post-checkout / post-rewrite), PATH independence
(the install-time binary is baked in), background + serialized rebuilds, and
the index-exists scope that leaves throwaway worktrees alone (#316).

The text tests read the generated hooks. The end-to-end tests drive real git
with a fake ``neuralmind`` that records every call, a minimal PATH that
cannot find it, and a deliberately slow ``build`` — so "git doesn't wait",
"works without neuralmind on PATH", "pulls and branch switches rebuild",
"bursts coalesce" and "worktrees stay untouched" are observed, not inferred.
"""

import argparse
import os
import shutil
import subprocess
import sys
import time
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from neuralmind.cli import cmd_init_hook

LIFECYCLE = ("post-merge", "post-checkout", "post-rewrite")
ALL_HOOKS = ("post-commit",) + LIFECYCLE
FAKE_BIN = "/opt/nm/bin/neuralmind"


def _install(project, monkeypatch, bin_path=FAKE_BIN, sync=False):
    # raising=False: the sabotage run (old cli.py, no such helper) must still
    # install the OLD hooks so the end-to-end tests fail on behavior.
    monkeypatch.setattr("neuralmind.cli._neuralmind_hook_binary", lambda: bin_path, raising=False)
    cmd_init_hook(
        argparse.Namespace(project_path=str(project), no_drift=True, strict=False, sync=sync)
    )


def _hook(project, name):
    return (project / ".git" / "hooks" / name).read_text()


def _block(text):
    return text[text.index("# neuralmind-hook-start") : text.index("# neuralmind-hook-end")]


@pytest.fixture
def project(tmp_path):
    (tmp_path / ".git" / "hooks").mkdir(parents=True)
    (tmp_path / ".neuralmind").mkdir()
    (tmp_path / ".neuralmind" / "build_status.json").write_text("{}")  # what a build writes
    return tmp_path


# ------------------------------------------------------------------ #
# Generated hook text
# ------------------------------------------------------------------ #


class TestHookText:
    def test_installs_the_lifecycle_hooks(self, project, monkeypatch, capsys):
        _install(project, monkeypatch)
        for name in LIFECYCLE:
            text = _hook(project, name)
            assert text.startswith("#!/bin/sh\n")
            assert text.count("# neuralmind-hook-start") == 1
            assert '"$_nm_bin" build .' in text
            assert "decisions scan" not in text  # only post-commit scans: it reads HEAD
        assert "Pulls, merges, branch switches and rebases" in capsys.readouterr().out

    def test_post_checkout_rebuilds_only_on_a_branch_switch_to_another_commit(
        self, project, monkeypatch
    ):
        _install(project, monkeypatch)
        assert '[ "$3" = "1" ] && [ "$1" != "$2" ]' in _hook(project, "post-checkout")

    def test_bakes_in_the_install_time_binary_with_a_path_fallback(
        self, project, monkeypatch, capsys
    ):
        _install(project, monkeypatch)
        for name in ALL_HOOKS:
            text = _hook(project, name)
            assert f"_nm_bin={FAKE_BIN}\n" in text
            assert '[ -x "$_nm_bin" ] || _nm_bin=$(command -v neuralmind 2>/dev/null)' in text
            assert "command -v neuralmind >/dev/null 2>&1; then" not in text  # the old guard
        assert f"They run {FAKE_BIN}" in capsys.readouterr().out

    def test_quotes_a_binary_path_with_spaces(self, project, monkeypatch):
        _install(project, monkeypatch, bin_path="/Users/a b/bin/neuralmind")
        assert "_nm_bin='/Users/a b/bin/neuralmind'" in _hook(project, "post-commit")

    @pytest.mark.parametrize("strict", [False, True])
    def test_the_drift_guard_uses_the_same_binary(self, project, monkeypatch, strict):
        """The pre-commit guard had the same `command -v` blind spot."""
        monkeypatch.setattr("neuralmind.cli._neuralmind_hook_binary", lambda: FAKE_BIN)
        cmd_init_hook(
            argparse.Namespace(project_path=str(project), no_drift=False, strict=strict, sync=False)
        )
        text = _hook(project, "pre-commit")
        assert f"_nm_bin={FAKE_BIN}\n" in text
        assert "command -v neuralmind >/dev/null 2>&1; then" not in text
        if strict:  # the drift status is the block's status: a drift blocks the commit
            assert '    "$_nm_bin" drift . --staged --strict\n' in text
        else:
            assert '    "$_nm_bin" drift . --staged || true\n' in text
        if shutil.which("sh"):
            path = project / ".git" / "hooks" / "pre-commit"
            assert subprocess.run(["sh", "-n", str(path)]).returncode == 0

    def test_without_an_install_path_it_falls_back_to_path_and_says_so(
        self, project, monkeypatch, capsys
    ):
        _install(project, monkeypatch, bin_path="")
        assert "_nm_bin=''" in _hook(project, "post-commit")
        assert "no install path was found" in capsys.readouterr().out

    def test_finds_the_script_in_the_interpreters_scripts_dir_when_off_path(
        self, tmp_path, monkeypatch
    ):
        """`python -m neuralmind init-hook` with the script off PATH still bakes it in."""
        import shutil as _shutil
        import sysconfig

        from neuralmind.cli import _neuralmind_hook_binary

        script = tmp_path / ("neuralmind.exe" if sys.platform.startswith("win") else "neuralmind")
        script.write_text("#!/bin/sh\n")
        script.chmod(0o755)
        monkeypatch.setattr(_shutil, "which", lambda name: None)
        monkeypatch.setattr(sysconfig, "get_path", lambda name: str(tmp_path))
        assert _neuralmind_hook_binary() == str(script)

    def test_rebuilds_only_a_built_project(self, project, monkeypatch):
        """Keyed on build_status.json, as session_recap._project_built() is: the
        session hooks create .neuralmind/ in any repository they run in."""
        _install(project, monkeypatch)
        for name in ALL_HOOKS:
            text = _hook(project, name)
            assert "[ -f ./.neuralmind/build_status.json ]" in text
            assert "[ -d ./.neuralmind ]" not in text
        # The scan keeps its own precondition: a decision store to scan.
        assert "[ -f ./.neuralmind/memory.db ]" in _hook(project, "post-commit")

    @pytest.mark.parametrize("session_dir", [False, True])
    def test_warns_when_the_project_has_no_index_yet(
        self, tmp_path, monkeypatch, capsys, session_dir
    ):
        (tmp_path / ".git" / "hooks").mkdir(parents=True)
        if session_dir:  # a session hook created .neuralmind/, but nothing was built
            (tmp_path / ".neuralmind" / "recaps").mkdir(parents=True)
        _install(tmp_path, monkeypatch)
        out = capsys.readouterr().out
        assert "No index yet" in out
        assert "neuralmind build ." in out

    def test_rebuilds_in_the_background_by_default(self, project, monkeypatch):
        _install(project, monkeypatch)
        text = _hook(project, "post-commit")
        assert 'mkdir "$_nm_dir/.hook-build.lock"' in text
        assert ") </dev/null >/dev/null 2>&1 &\n" in text
        assert "hook-build.log" in text
        assert "unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_PREFIX" in text
        # The decision scan stays synchronous and runs before the rebuild.
        assert text.index('"$_nm_bin" decisions scan . --quiet || true') < text.index(
            '"$_nm_bin" build .'
        )

    def test_sync_keeps_the_foreground_rebuild(self, project, monkeypatch, capsys):
        _install(project, monkeypatch, sync=True)
        for name in ALL_HOOKS:
            block = _block(_hook(project, name))
            assert ".hook-build.lock" not in block
            assert "&\n" not in block
        assert "[neuralmind] OK" in _hook(project, "post-commit")
        assert "git waits: --sync" in capsys.readouterr().out

    def test_mock_args_do_not_turn_on_sync(self, project, monkeypatch):
        """A MagicMock attribute is truthy; only a real --sync flag opts out."""
        monkeypatch.setattr("neuralmind.cli._neuralmind_hook_binary", lambda: FAKE_BIN)
        args = MagicMock()
        args.project_path = str(project)
        args.no_drift = True
        cmd_init_hook(args)
        assert ".hook-build.lock" in _hook(project, "post-commit")

    def test_blocks_never_exit_so_other_hook_content_keeps_running(self, project, monkeypatch):
        lfs = (
            '#!/bin/sh\ncommand -v git-lfs >/dev/null 2>&1 || exit 0\ngit lfs post-checkout "$@"\n'
        )
        (project / ".git" / "hooks" / "post-checkout").write_text(lfs)
        _install(project, monkeypatch)
        assert _hook(project, "post-checkout").startswith(lfs)
        for name in ALL_HOOKS:
            assert "exit" not in _block(_hook(project, name))

    def test_idempotent_for_every_hook(self, project, monkeypatch):
        _install(project, monkeypatch)
        _install(project, monkeypatch)
        for name in ALL_HOOKS:
            text = _hook(project, name)
            assert text.count("# neuralmind-hook-start") == 1
            assert text.count("# neuralmind-hook-end") == 1

    @pytest.mark.skipif(shutil.which("sh") is None, reason="needs a POSIX shell")
    @pytest.mark.parametrize("sync", [False, True])
    def test_generated_hooks_parse(self, project, monkeypatch, sync):
        _install(project, monkeypatch, sync=sync)
        for name in ALL_HOOKS:
            path = project / ".git" / "hooks" / name
            assert subprocess.run(["sh", "-n", str(path)]).returncode == 0, name


# ------------------------------------------------------------------ #
# End to end: real git, fake neuralmind, minimal PATH
# ------------------------------------------------------------------ #

GIT = shutil.which("git")
FAKE = """#!/bin/sh
echo "$(pwd -P)|$*" >> "$NM_FAKE_LOG"
case "$1" in
    build) sleep "${NM_FAKE_BUILD_SECONDS:-0}" ;;
    drift) exit "${NM_FAKE_DRIFT_RC:-0}" ;;
esac
exit 0
"""

e2e = pytest.mark.skipif(
    sys.platform.startswith("win") or GIT is None, reason="POSIX git hooks need git and sh"
)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    assert GIT is not None
    fake = tmp_path / "nm-bin" / "neuralmind"
    fake.parent.mkdir()
    fake.write_text(FAKE)
    fake.chmod(0o755)
    root = tmp_path / "repo"
    root.mkdir()
    log = tmp_path / "calls.log"
    env = {
        # The fake is NOT on this PATH: only the baked-in path can reach it.
        "PATH": "/usr/bin:/bin",
        "HOME": str(tmp_path),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.com",
        "NM_FAKE_LOG": str(log),
        "NM_FAKE_BUILD_SECONDS": "0",
    }

    def git(*args, cwd=root):
        out = subprocess.run(
            [GIT, *args], cwd=cwd, env=env, capture_output=True, text=True, timeout=60
        )
        assert out.returncode == 0, out.stderr
        return out

    git("init", "-q", "-b", "main")
    (root / "a.py").write_text("x = 1\n")
    git("add", "a.py")
    git("commit", "-q", "-m", "init")  # before any hook exists
    (root / ".neuralmind").mkdir()
    (root / ".neuralmind" / "build_status.json").write_text("{}")  # built
    (root / ".neuralmind" / "memory.db").write_text("")  # has a decision store
    _install(root, monkeypatch, bin_path=str(fake))
    return SimpleNamespace(root=root, git=git, env=env, log=log, tmp=tmp_path)


def _calls(r):
    return r.log.read_text().splitlines() if r.log.exists() else []


def _builds(r, where=None):
    where = os.path.realpath(where or r.root)
    return [c for c in _calls(r) if c == f"{where}|build ."]


def _settle(r, timeout=20):
    """Wait until no hook build is running (lock gone)."""
    lock = r.root / ".neuralmind" / ".hook-build.lock"
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not lock.exists():
            return
        time.sleep(0.1)
    raise AssertionError("hook build lock never released")


def _wait_for(predicate, timeout=20):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.1)
    return False


@e2e
class TestHooksEndToEnd:
    def test_commit_returns_before_the_rebuild_and_needs_no_path(self, repo):
        repo.env["NM_FAKE_BUILD_SECONDS"] = "4"
        t0 = time.time()
        repo.git("commit", "-q", "--allow-empty", "-m", "c1")
        assert time.time() - t0 < 3, "git waited for the rebuild"
        assert _wait_for(lambda: _builds(repo)), "the background rebuild never ran"
        calls = _calls(repo)
        root = os.path.realpath(repo.root)
        assert calls.index(f"{root}|decisions scan . --quiet") < calls.index(f"{root}|build .")
        _settle(repo)

    def test_branch_switch_merge_and_rewrite_rebuild_but_file_checkout_does_not(self, repo):
        repo.git("checkout", "-q", "-b", "feature")  # same commit: nothing to rebuild
        time.sleep(1)
        assert _builds(repo) == []
        (repo.root / "b.py").write_text("y = 2\n")
        repo.git("add", "b.py")
        repo.git("commit", "-q", "-m", "feature work")  # post-commit
        assert _wait_for(lambda: len(_builds(repo)) == 1)
        _settle(repo)

        repo.git("checkout", "-q", "main")  # branch switch to another commit
        assert _wait_for(lambda: len(_builds(repo)) == 2), "post-checkout did not rebuild"
        _settle(repo)

        repo.git("merge", "-q", "--ff-only", "feature")  # what a pull does
        assert _wait_for(lambda: len(_builds(repo)) == 3), "post-merge did not rebuild"
        _settle(repo)

        repo.git("checkout", "-q", "--", "a.py")  # file checkout (flag 0)
        time.sleep(1)
        assert len(_builds(repo)) == 3

        hook = repo.root / ".git" / "hooks" / "post-rewrite"
        subprocess.run(["sh", str(hook), "rebase"], cwd=repo.root, env=repo.env, check=True)
        assert _wait_for(lambda: len(_builds(repo)) == 4), "post-rewrite did not rebuild"
        _settle(repo)

    def test_a_throwaway_worktree_is_left_alone(self, repo):
        wt = repo.tmp / "wt"
        repo.git("worktree", "add", "-q", "-b", "wt", str(wt))  # fires post-checkout in wt
        # A Claude Code session in the worktree: its hooks create .neuralmind/
        # in any repository they run in — that must not make it look built.
        (wt / ".neuralmind" / "recaps").mkdir(parents=True)
        repo.git("commit", "-q", "--allow-empty", "-m", "in worktree", cwd=wt)
        time.sleep(1.5)
        assert not (wt / ".neuralmind" / "build_status.json").exists()
        assert not (wt / ".neuralmind" / "hook-build.log").exists()
        assert not [c for c in _calls(repo) if c.startswith(os.path.realpath(wt) + "|")]
        # Positive control: the same shared hooks DO rebuild the indexed main
        # checkout, so the worktree was skipped by scope, not by dead hooks.
        repo.git("commit", "-q", "--allow-empty", "-m", "in main")
        assert _wait_for(
            lambda: _builds(repo)
        ), "hooks are dead, so the worktree check proves nothing"
        _settle(repo)

    def test_overlapping_events_coalesce_into_one_extra_build(self, repo):
        repo.env["NM_FAKE_BUILD_SECONDS"] = "2"
        for i in range(3):
            repo.git("commit", "-q", "--allow-empty", "-m", f"burst {i}")
        _settle(repo, timeout=30)
        assert len(_builds(repo)) == 2, _calls(repo)  # the first, plus one for the queued two
        assert not (repo.root / ".neuralmind" / ".hook-build.pending").exists()

    def test_a_stale_lock_from_a_dead_build_is_cleared(self, repo):
        lock = repo.root / ".neuralmind" / ".hook-build.lock"
        lock.mkdir()
        two_hours_ago = time.time() - 7200
        os.utime(lock, (two_hours_ago, two_hours_ago))
        repo.git("commit", "-q", "--allow-empty", "-m", "after a crash")
        assert _wait_for(lambda: _builds(repo)), "a dead build's lock blocked rebuilds forever"
        _settle(repo)

    def test_a_strict_drift_guard_blocks_even_without_neuralmind_on_path(self, repo, monkeypatch):
        """The old guard's `command -v` skipped silently here and let the commit through."""
        fake = str(repo.tmp / "nm-bin" / "neuralmind")
        monkeypatch.setattr("neuralmind.cli._neuralmind_hook_binary", lambda: fake, raising=False)
        cmd_init_hook(
            argparse.Namespace(project_path=str(repo.root), no_drift=False, strict=True, sync=False)
        )
        repo.env["NM_FAKE_DRIFT_RC"] = "1"
        out = subprocess.run(
            [GIT, "commit", "-q", "--allow-empty", "-m", "drifts"],
            cwd=repo.root,
            env=repo.env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert out.returncode != 0, "the strict drift guard was skipped: the commit went through"
        assert any(c.endswith("|drift . --staged --strict") for c in _calls(repo))

    def test_sync_makes_git_wait_for_the_build(self, repo, monkeypatch):
        _install(
            repo.root, monkeypatch, bin_path=str(repo.tmp / "nm-bin" / "neuralmind"), sync=True
        )
        repo.env["NM_FAKE_BUILD_SECONDS"] = "2"
        t0 = time.time()
        repo.git("commit", "-q", "--allow-empty", "-m", "sync")
        assert time.time() - t0 >= 2
        assert _builds(repo)  # already there when git returned
