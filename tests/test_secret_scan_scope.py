"""scan-for-secrets scope inside a git repository (#635).

Real git, real worktrees: a linked worktree inside the checkout repeated every
finding once per worktree, and gitignored files the index never sees (an
untracked ``.env``) were reported beside committed credentials with nothing to
tell them apart. The scan now covers what ``build`` indexes, skips linked
worktrees, says what it left out, and marks each finding tracked or not.

Stdlib-only, like the rest of the scanner's tests.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from argparse import Namespace

import pytest

from neuralmind.secret_scan import _is_linked_worktree, scan_project, scan_project_report
from tests.secret_fixtures import ANTHROPIC_KEY, AWS_KEY_ID

GIT = shutil.which("git")
pytestmark = pytest.mark.skipif(GIT is None, reason="needs git")

_ENV = {
    **os.environ,
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.com",
}


def _git(cwd, *args):
    assert GIT is not None
    out = subprocess.run(
        [GIT, *args], cwd=cwd, env=_ENV, capture_output=True, text=True, timeout=60
    )
    assert out.returncode == 0, out.stderr
    return out.stdout


@pytest.fixture
def repo(tmp_path):
    """A repo with one committed credential, an ignored .env and an untracked file."""
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    (root / ".gitignore").write_text(".env\n")
    (root / "conf.py").write_text(f"KEY = '{AWS_KEY_ID}'\n")
    _git(root, "add", ".gitignore", "conf.py")
    _git(root, "commit", "-q", "-m", "init")
    (root / ".env").write_text(f"ANTHROPIC_API_KEY={ANTHROPIC_KEY}\n")
    (root / "scratch.py").write_text(f"TOKEN = '{ANTHROPIC_KEY}'\n")
    return root


def _paths(findings):
    return sorted(f.path.replace("\\", "/") for f in findings)


class TestLinkedWorktrees:
    def test_a_worktree_inside_the_checkout_is_scanned_once_not_twice(self, repo):
        """The field report: every finding repeated once per `.worktrees/<id>/`."""
        _git(repo, "worktree", "add", "-q", "-b", "w1", ".worktrees/w1")
        _git(repo, "worktree", "add", "-q", "-b", "w2", ".claude/worktrees/w2")
        report = scan_project_report(repo)
        assert _paths(report.findings) == ["conf.py", "scratch.py"]
        assert report.skipped_worktrees == [".claude/worktrees/w2", ".worktrees/w1"]

    def test_full_sweep_still_skips_worktrees(self, repo):
        _git(repo, "worktree", "add", "-q", "-b", "w1", ".worktrees/w1")
        report = scan_project_report(repo, respect_gitignore=False)
        assert ".worktrees/w1/conf.py" not in _paths(report.findings)

    def test_a_submodule_is_still_scanned(self, repo, tmp_path):
        """A submodule's `.git` is a file too, but it is separate code build indexes."""
        lib = tmp_path / "lib"
        lib.mkdir()
        _git(lib, "init", "-q", "-b", "main")
        (lib / "creds.py").write_text(f"KEY = '{AWS_KEY_ID}'\n")
        _git(lib, "add", "creds.py")
        _git(lib, "commit", "-q", "-m", "lib")
        _git(repo, "-c", "protocol.file.allow=always", "submodule", "add", "-q", str(lib), "lib")
        assert (repo / "lib" / ".git").is_file()
        assert not _is_linked_worktree(repo / "lib")
        report = scan_project_report(repo)
        assert "lib/creds.py" in _paths(report.findings)
        assert report.skipped_worktrees == []
        assert next(f for f in report.findings if f.path.endswith("creds.py")).tracked is True

    def test_a_nested_repository_is_still_scanned(self, repo):
        nested = repo / "vendor" / "tool"
        nested.mkdir(parents=True)
        _git(nested, "init", "-q", "-b", "main")
        (nested / "k.py").write_text(f"KEY = '{AWS_KEY_ID}'\n")
        assert "vendor/tool/k.py" in _paths(scan_project(repo))

    def test_a_worktree_whose_gitdir_is_gone_is_still_recognised(self, tmp_path):
        wt = tmp_path / "wt"
        wt.mkdir()
        (wt / ".git").write_text("gitdir: /gone/repo/.git/worktrees/wt\n")
        assert _is_linked_worktree(wt)

    def test_plain_directories_are_not_worktrees(self, tmp_path):
        assert not _is_linked_worktree(tmp_path)
        (tmp_path / ".git").mkdir()
        assert not _is_linked_worktree(tmp_path)  # a repository, not a linked worktree


class TestGitignore:
    def test_ignored_files_are_skipped_and_counted(self, repo):
        report = scan_project_report(repo)
        assert ".env" not in _paths(report.findings)
        assert report.ignored_files_skipped == 1
        assert report.git is True

    def test_include_ignored_scans_them_too(self, repo):
        report = scan_project_report(repo, respect_gitignore=False)
        assert _paths(report.findings) == [".env", "conf.py", "scratch.py"]
        assert report.ignored_files_skipped == 0

    def test_outside_git_everything_is_scanned(self, tmp_path):
        (tmp_path / ".gitignore").write_text(".env\n")
        (tmp_path / ".env").write_text(f"ANTHROPIC_API_KEY={ANTHROPIC_KEY}\n")
        report = scan_project_report(tmp_path)
        assert _paths(report.findings) == [".env"]
        assert report.git is False
        assert report.findings[0].tracked is None


class TestTracked:
    def test_each_finding_says_whether_git_tracks_its_file(self, repo):
        by_path = {f.path.replace("\\", "/"): f.tracked for f in scan_project(repo)}
        assert by_path == {"conf.py": True, "scratch.py": False}

    def test_a_project_in_a_subdirectory_reports_its_own_relative_paths(self, repo):
        sub = repo / "svc"
        sub.mkdir()
        (sub / "app.py").write_text(f"KEY = '{AWS_KEY_ID}'\n")
        _git(repo, "add", "svc/app.py")
        _git(repo, "commit", "-q", "-m", "svc")
        findings = scan_project(sub)
        assert [(f.path.replace("\\", "/"), f.tracked) for f in findings] == [("app.py", True)]


class TestCli:
    @staticmethod
    def _run(path, capsys, **overrides):
        from neuralmind.cli import cmd_scan_for_secrets

        args = Namespace(
            project_path=str(path),
            high_confidence_only=False,
            strict=False,
            use_neuralmindignore=False,
            include_ignored=False,
            json=False,
        )
        for k, v in overrides.items():
            setattr(args, k, v)
        try:
            cmd_scan_for_secrets(args)
            code = 0
        except SystemExit as exc:
            code = exc.code
        return code, capsys.readouterr().out

    def test_text_output_marks_tracking_and_says_what_was_skipped(self, repo, capsys):
        _git(repo, "worktree", "add", "-q", "-b", "w1", ".worktrees/w1")
        code, out = self._run(repo, capsys)
        assert code == 1
        assert "conf.py:1" in out and "[tracked]" in out
        assert "scratch.py:1" in out and "[untracked]" in out
        assert "2 high-confidence (1 in tracked files)" in out
        assert "Skipped 1 linked worktree (.worktrees/w1)" in out
        assert "Skipped 1 file that .gitignore excludes" in out
        assert "--include-ignored" in out
        assert ".worktrees/w1/conf.py" not in out

    def test_a_clean_scan_still_says_what_it_left_out(self, tmp_path, capsys):
        root = tmp_path / "r"
        root.mkdir()
        _git(root, "init", "-q", "-b", "main")
        (root / ".gitignore").write_text(".env\n")
        (root / ".env").write_text(f"ANTHROPIC_API_KEY={ANTHROPIC_KEY}\n")
        code, out = self._run(root, capsys)
        assert code == 0
        assert "No credentials detected." in out
        assert "Skipped 1 file that .gitignore excludes" in out

    def test_include_ignored_flag(self, repo, capsys):
        code, out = self._run(repo, capsys, include_ignored=True, json=True)
        payload = json.loads(out)
        assert code == 1
        assert sorted(f["path"] for f in payload["findings"]) == [".env", "conf.py", "scratch.py"]
        assert payload["gitignore_respected"] is False
        assert payload["ignored_files_skipped"] == 0

    def test_json_carries_tracked_and_the_skips(self, repo, capsys):
        _git(repo, "worktree", "add", "-q", "-b", "w1", ".worktrees/w1")
        _, out = self._run(repo, capsys, json=True)
        payload = json.loads(out)
        assert {f["path"]: f["tracked"] for f in payload["findings"]} == {
            "conf.py": True,
            "scratch.py": False,
        }
        assert payload["gitignore_respected"] is True
        assert payload["ignored_files_skipped"] == 1
        assert payload["skipped_worktrees"] == [".worktrees/w1"]

    def test_the_flag_is_wired_into_the_parser(self):
        import sys
        from unittest.mock import patch

        from neuralmind import cli

        seen = {}
        with patch.object(cli, "cmd_scan_for_secrets", side_effect=lambda a: seen.update(vars(a))):
            with patch.object(
                sys, "argv", ["neuralmind", "scan-for-secrets", ".", "--include-ignored"]
            ):
                try:
                    cli.main()
                except SystemExit:
                    pass
        assert seen.get("include_ignored") is True
