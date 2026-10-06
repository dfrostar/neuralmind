"""review / ci-check / drift read git diffs relative to the *project*, not the repo.

``git diff --name-only`` prints paths relative to the repository root. For a
project in a subdirectory of a larger repository (``services/billing`` in a
monorepo) those paths were joined onto the project path as if they were
project-relative — ``services/billing/services/billing/pkg/payments.py`` —
so ``review`` found nothing at risk ("Looks complete."), ``drift`` checked 0
symbols, and ``ci-check`` skipped every changed file. Paths must come back
relative to the project, and changes outside it must be dropped.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")

SUB = "services/billing"

PAYMENTS = '''from pkg.ledger import post_entry, reverse_entry


def charge(amount):
    """Charge a card and record it."""
    return post_entry("charge", amount)


def refund(amount):
    """Refund a charge."""
    return reverse_entry("charge", amount)
'''

LEDGER = '''def post_entry(kind, amount):
    """Post a ledger entry."""
    return {"kind": kind, "amount": amount}


def reverse_entry(kind, amount):
    """Reverse a ledger entry."""
    return {"kind": kind, "amount": -amount}
'''

VOID = '''

def void(amount):
    """Void a charge."""
    return post_entry("void", amount)
'''


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@example.com",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@example.com",
        },
    ).stdout


def _monorepo(root: Path, *, commit: bool = True) -> Path:
    """Repo at ``root`` with the billing project at ``root/services/billing``."""
    project = root / SUB
    (project / "pkg").mkdir(parents=True)
    (project / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (project / "pkg" / "payments.py").write_text(PAYMENTS, encoding="utf-8")
    (project / "pkg" / "ledger.py").write_text(LEDGER, encoding="utf-8")
    (root / "services" / "other").mkdir(parents=True)
    (root / "services" / "other" / "worker.py").write_text("x = 1\n", encoding="utf-8")
    (root / "README.md").write_text("# monorepo\n", encoding="utf-8")
    (root / ".gitignore").write_text(".neuralmind/\n", encoding="utf-8")
    _git(root, "init", "-q")
    if commit:
        _git(root, "add", "-A")
        _git(root, "commit", "-q", "-m", "init")
    return project


def _change_outside(root: Path) -> None:
    (root / "README.md").write_text("# monorepo, edited\n", encoding="utf-8")
    (root / "services" / "other" / "worker.py").write_text("x = 2\n", encoding="utf-8")


def _add_void(project: Path) -> None:
    payments = project / "pkg" / "payments.py"
    payments.write_text(payments.read_text(encoding="utf-8") + VOID, encoding="utf-8")


@pytest.fixture
def built_monorepo(tmp_path):
    """A committed monorepo whose billing project has a NeuralMind index."""
    pytest.importorskip("turbovec")
    from neuralmind import graphgen

    if not graphgen.is_available():
        pytest.skip("tree-sitter not installed")
    from tests.test_index_freshness import _mind

    project = _monorepo(tmp_path)
    _mind(project).build()
    return tmp_path, project


# --------------------------------------------------------------------------- #
# review
# --------------------------------------------------------------------------- #


def _review(project: Path, monkeypatch) -> dict:
    from neuralmind import cli
    from tests.test_index_freshness import _mind

    def _ready(path, auto_build=True):
        mind = _mind(Path(path))
        mind.ensure_ready()
        return mind

    monkeypatch.setattr(cli, "create_mind", _ready)
    args = SimpleNamespace(project_path=str(project), base="HEAD", top_k=10, json=True)
    out = io.StringIO()
    with redirect_stdout(out):
        cli.cmd_review(args)
    return json.loads(out.getvalue())


def test_review_in_subproject_finds_associated_file(built_monorepo, monkeypatch):
    root, project = built_monorepo
    _add_void(project)
    _change_outside(root)

    report = _review(project, monkeypatch)

    assert report["changed_files"] == ["pkg/payments.py"]
    assert "pkg/ledger.py" in [item["file"] for item in report["at_risk"]]


def test_review_in_subproject_ignores_changes_outside_it(built_monorepo, monkeypatch):
    root, project = built_monorepo
    _change_outside(root)

    report = _review(project, monkeypatch)

    assert report["changed_files"] == []
    assert report["message"] == "no changed files"


# --------------------------------------------------------------------------- #
# ci-check
# --------------------------------------------------------------------------- #


def test_ci_check_diff_files_are_project_relative(tmp_path):
    from neuralmind import ci_check

    project = _monorepo(tmp_path)
    _add_void(project)
    _change_outside(tmp_path)

    assert ci_check._get_diff_files(project) == ["pkg/payments.py"]
    # At the repository root nothing is outside the project.
    assert sorted(ci_check._get_diff_files(tmp_path)) == [
        "README.md",
        f"{SUB}/pkg/payments.py",
        "services/other/worker.py",
    ]


def test_ci_check_staged_fallback_is_project_relative(tmp_path):
    """No HEAD yet, so `git diff HEAD` fails and the staged diff is used."""
    from neuralmind import ci_check

    project = _monorepo(tmp_path, commit=False)
    _git(tmp_path, "add", "-A")

    assert sorted(ci_check._get_diff_files(project)) == [
        "pkg/__init__.py",
        "pkg/ledger.py",
        "pkg/payments.py",
    ]


def test_ci_check_reports_annotation_in_subproject(tmp_path):
    from neuralmind import ci_check

    project = _monorepo(tmp_path)
    payments = project / "pkg" / "payments.py"
    payments.write_text(
        "# CMMC AC.L2-3.1.1: Authorized Access Control\n" + PAYMENTS, encoding="utf-8"
    )

    result = ci_check.run_ci_check(project, framework="cmmc")

    assert result["changed_files"] == 1
    assert [f["file"] for f in result["findings"]] == ["pkg/payments.py"]
    assert result["affected_controls"] == ["AC.L2-3.1.1"]


# --------------------------------------------------------------------------- #
# drift
# --------------------------------------------------------------------------- #


def test_drift_diff_headers_are_project_relative(tmp_path):
    from neuralmind import drift

    project = _monorepo(tmp_path)
    _add_void(project)
    _change_outside(tmp_path)

    ranges = drift.parse_diff_hunks(drift.diff_text(project))
    assert list(ranges) == ["pkg/payments.py"]

    _git(tmp_path, "add", "-A")
    staged = drift.parse_diff_hunks(drift.diff_text(project, staged=True))
    assert list(staged) == ["pkg/payments.py"]


def test_drift_checks_symbols_in_subproject(built_monorepo):
    from neuralmind import drift

    root, project = built_monorepo
    payments = project / "pkg" / "payments.py"
    payments.write_text(
        payments.read_text(encoding="utf-8").replace("Refund a charge.", "Refund a payment."),
        encoding="utf-8",
    )
    _change_outside(root)

    result = drift.check_project(str(project), refresh=False)

    assert result["changed_files"] == ["pkg/payments.py"]
    assert result["graph"] == "loaded"
    assert result["symbols_checked"] >= 1
