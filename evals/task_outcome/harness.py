"""Workspace and test-oracle helpers shared by ``harvest`` and ``run``.

Every task is a real bug fix from a repository's history: this one by
default, another clone after ``use_repo`` (``--repo``). The agent works on
a snapshot of the fix's *parent* commit and never sees the fix, its tests, or
the later history: ``snapshot`` exports the tree with ``git archive`` into a
fresh repository with a single commit, so ``git log`` shows nothing to copy.
The oracle is the fix's own tests, applied only after the agent stops.

Stdlib only.
"""

from __future__ import annotations

import hashlib
import io
import os
import subprocess
import tarfile
import xml.etree.ElementTree as ET
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def use_repo(path: Path) -> None:
    """Draw tasks from another clone (``--repo``); the default is this repository."""
    global REPO
    REPO = Path(path).resolve()


def git(*args: str, cwd: Path | None = None, input_bytes: bytes | None = None) -> bytes:
    return subprocess.run(
        ["git", *args], cwd=cwd or REPO, input=input_bytes, capture_output=True, check=True
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


def test_key(test_id: str) -> str:
    """``test_id`` with any parametrize suffix replaced by a short digest.

    The secret-scanner tests are parametrized with fake credentials, and pytest
    puts the parameter in the test's name. Stored literally, the oracle would
    hold credential-shaped strings, which push protection rightly blocks; the
    digest keeps each case distinct without them.
    """
    base, sep, param = test_id.partition("[")
    if not sep:
        return test_id
    return f"{base}[{hashlib.sha256(param.rstrip(']').encode()).hexdigest()[:12]}]"


def run_tests(
    workspace: Path,
    test_files: list[str],
    python: str,
    timeout: int = 900,
    extra_env: dict[str, str] | None = None,
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
    env.update(extra_env or {})
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
        test_id = test_key(f"{case.get('classname')}::{case.get('name')}")
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


def workspace_env(
    workspace: Path, isolated_hermes_home: bool, create: bool = True
) -> dict[str, str]:
    """Variables every process in ``workspace`` gets: a HERMES_HOME of its own, if asked.

    Hermes-Agent's code re-publishes its launchers for the active HERMES_HOME;
    pointing it at a directory inside the workspace keeps a user's real Hermes
    home out of the benchmark (see ``launcher_digest``).
    """
    if not isolated_hermes_home:
        return {}
    home = workspace / ".bench-hermes-home"
    if create:
        home.mkdir(parents=True, exist_ok=True)
    return {"HERMES_HOME": str(home)}


def launcher_digest(dirs: list[Path]) -> dict[str, str]:
    """SHA-256 of every file under ``dirs``: compared before and after each run.

    A run that changed one of them (a real Hermes install's launchers, say)
    stops the benchmark before it is recorded.
    """
    digest: dict[str, str] = {}
    for root in dirs:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if path.is_file():
                digest[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest
