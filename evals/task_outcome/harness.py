"""Workspace and test-oracle helpers shared by ``harvest`` and ``run``.

Every task is a real bug fix from this repository's history. The agent works on
a snapshot of the fix's *parent* commit and never sees the fix, its tests, or
the later history: ``snapshot`` exports the tree with ``git archive`` into a
fresh repository with a single commit, so ``git log`` shows nothing to copy.
The oracle is the fix's own tests, applied only after the agent stops.

Stdlib only.
"""

from __future__ import annotations

import io
import os
import subprocess
import tarfile
import xml.etree.ElementTree as ET
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def git(*args: str, cwd: Path = REPO, input_bytes: bytes | None = None) -> bytes:
    return subprocess.run(
        ["git", *args], cwd=cwd, input=input_bytes, capture_output=True, check=True
    ).stdout


def parent_of(commit: str) -> str:
    return git("rev-parse", f"{commit}^").decode().strip()


def changed_files(commit: str) -> list[str]:
    out = git("diff-tree", "--no-commit-id", "--name-only", "-r", commit).decode()
    return [line for line in out.splitlines() if line]


def test_files_of(commit: str) -> list[str]:
    """Files under ``tests/`` the fix changed and that still exist after it."""
    keep = []
    for path in changed_files(commit):
        if not path.startswith("tests/"):
            continue
        try:
            git("cat-file", "-e", f"{commit}:{path}")
        except subprocess.CalledProcessError:
            continue  # deleted by the fix
        keep.append(path)
    return keep


def snapshot(commit: str, dest: Path) -> Path:
    """Export ``commit``'s tree to ``dest`` as a one-commit repository."""
    dest.mkdir(parents=True, exist_ok=False)
    archive = git("archive", "--format=tar", commit)

    def keep(member: tarfile.TarInfo, path: str) -> tarfile.TarInfo | None:
        # Old commits hold a symlink to an absolute path, which the "data"
        # filter refuses; the link is dropped and the rest extracts as data.
        try:
            return tarfile.data_filter(member, path)
        except tarfile.AbsoluteLinkError:
            return None

    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(dest, filter=keep)
    env = {**os.environ, "GIT_AUTHOR_DATE": "2000-01-01T00:00:00Z"}
    env["GIT_COMMITTER_DATE"] = env["GIT_AUTHOR_DATE"]
    for args in (
        ["init", "-q", "-b", "main"],
        ["add", "-A"],
        [
            "-c",
            "user.name=bench",
            "-c",
            "user.email=bench@localhost",
            "commit",
            "-q",
            "-m",
            "snapshot",
        ],
    ):
        subprocess.run(["git", *args], cwd=dest, env=env, capture_output=True, check=True)
    return dest


def overlay(commit: str, paths: list[str], dest: Path) -> None:
    """Write ``commit``'s version of each path into ``dest``."""
    for path in paths:
        target = dest / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(git("show", f"{commit}:{path}"))


def run_tests(
    workspace: Path, test_files: list[str], python: str, timeout: int = 900
) -> dict[str, str]:
    """Run ``test_files`` in ``workspace``; return ``{test_id: outcome}``.

    ``python -m pytest`` from the workspace root puts the workspace on
    ``sys.path``, so the tests import the workspace's package, not an installed
    one. Outcomes are ``passed``, ``failed``, ``error`` or ``skipped``. A run
    that produces no report (collection crash, timeout) returns ``{}``.
    """
    report = workspace / ".bench-junit.xml"
    report.unlink(missing_ok=True)
    env = {
        k: v for k, v in os.environ.items() if k != "PYTHONPATH" and not k.startswith("NEURALMIND_")
    }
    try:
        subprocess.run(
            [python, "-m", "pytest", "-p", "no:cacheprovider", f"--junitxml={report}", *test_files],
            cwd=workspace,
            env=env,
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {}
    if not report.is_file():
        return {}
    outcomes: dict[str, str] = {}
    for case in ET.parse(report).getroot().iter("testcase"):
        test_id = f"{case.get('classname')}::{case.get('name')}"
        if case.find("failure") is not None:
            outcomes[test_id] = "failed"
        elif case.find("error") is not None:
            outcomes[test_id] = "error"
        elif case.find("skipped") is not None:
            outcomes[test_id] = "skipped"
        else:
            outcomes[test_id] = "passed"
    report.unlink(missing_ok=True)
    return outcomes
