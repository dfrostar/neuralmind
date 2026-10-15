"""``Decision:`` trailers get the decision store's lifecycle.

A trailer is committed history and can't be edited, so before this the
decision it records was recalled into every matching prompt for as long as it
stayed in the last 300 commits, with no way to retract it. ``decisions scan``
now imports each trailer into the store under a stable id, and the prompt
hooks (Claude Code's ``UserPromptSubmit``, the Hermes plugin's
``pre_llm_call``) and ``neuralmind why`` leave out the ones the store holds as
INVALIDATED and mark the STALE ones.
"""

from __future__ import annotations

import json
import subprocess

import pytest

from neuralmind.cli import build_parser
from neuralmind.hooks import _decisions_for_prompt
from neuralmind.memory.store import DecisionStore
from neuralmind.provenance import (
    harvest,
    import_trailers,
    parse_decision,
    trailer_decision_id,
    with_lifecycle,
)

TRAILER = "Decision: `upload_with_retry` keeps retries in the uploader, not the HTTP client."
PROMPT = "why does upload_with_retry retry here?"


def _git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def _commit(repo, path, text, message):
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", message)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.delenv("NEURALMIND_DECISION_SCAN", raising=False)
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test")
    _commit(tmp_path, "src/uploader.py", "def upload_with_retry(): ...\n", "initial")
    _commit(
        tmp_path,
        "src/uploader.py",
        "def upload_with_retry():\n    retry()\n",
        f"feat: retry uploads\n\n{TRAILER}",
    )
    return tmp_path


def _scan(repo, capsys, *extra):
    args = build_parser().parse_args(["decisions", "scan", str(repo), *extra])
    args.func(args)
    return capsys.readouterr().out


def _trailer_id():
    return trailer_decision_id(parse_decision(f"x\n\n{TRAILER}"))


def test_scan_imports_the_trailer_with_its_commit_files(repo, capsys):
    payload = json.loads(_scan(repo, capsys, "--json"))
    assert payload["imported"] == [_trailer_id()]
    record = DecisionStore(str(repo)).get(_trailer_id())
    assert record.status == "ACTIVE"
    assert record.commit_sha == _git(repo, "rev-parse", "HEAD")
    assert record.files_affected == ["src/uploader.py"]
    assert record.tags == ["trailer"]
    # The commit that carries the decision doesn't make it stale.
    assert payload["stale"] == []


def test_scan_import_is_idempotent(repo, capsys):
    _scan(repo, capsys)
    assert json.loads(_scan(repo, capsys, "--json"))["imported"] == []


def test_invalidated_trailer_leaves_the_prompt(repo, capsys):
    assert "upload_with_retry" in _decisions_for_prompt(str(repo), PROMPT)
    _scan(repo, capsys)
    DecisionStore(str(repo)).invalidate(_trailer_id(), reason="retries moved to the client")
    assert _decisions_for_prompt(str(repo), PROMPT) == ""


def test_reimport_never_revives_an_invalidated_trailer(repo, capsys):
    _scan(repo, capsys)
    store = DecisionStore(str(repo))
    store.invalidate(_trailer_id(), reason="superseded")
    assert import_trailers(store, str(repo), harvest(str(repo))) == []
    assert store.get(_trailer_id()).status == "INVALIDATED"


def test_a_later_commit_marks_the_trailer_stale(repo, capsys):
    _scan(repo, capsys)
    _commit(repo, "src/uploader.py", "def upload_with_retry():\n    pass\n", "drop retry")
    out = _scan(repo, capsys)
    assert "1 decision(s) marked STALE" in out
    block = _decisions_for_prompt(str(repo), PROMPT)
    assert "upload_with_retry" in block
    assert "[STALE:" in block


def test_restored_trailer_is_shown_without_the_warning(repo, capsys):
    _scan(repo, capsys)
    store = DecisionStore(str(repo))
    store.invalidate(_trailer_id())
    store.restore(_trailer_id(), new_commit_sha=_git(repo, "rev-parse", "HEAD"))
    block = _decisions_for_prompt(str(repo), PROMPT)
    assert "upload_with_retry" in block
    assert "STALE" not in block


def test_why_leaves_out_invalidated_trailers(repo, capsys):
    _scan(repo, capsys)
    DecisionStore(str(repo)).invalidate(_trailer_id())
    args = build_parser().parse_args(["why", "upload_with_retry", "--project-path", str(repo)])
    args.func(args)
    assert "No recorded decisions match" in capsys.readouterr().out


def test_without_a_store_recall_is_unchanged_and_creates_none(repo):
    records = harvest(str(repo))
    assert with_lifecycle(str(repo), records) == records
    assert "upload_with_retry" in _decisions_for_prompt(str(repo), PROMPT)
    assert not (repo / ".neuralmind").exists()


def test_scan_without_trailers_or_store_still_creates_none(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("NEURALMIND_DECISION_SCAN", raising=False)
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test")
    _commit(tmp_path, "a.py", "x = 1\n", "initial")
    assert "no decisions recorded" in _scan(tmp_path, capsys)
    assert not (tmp_path / ".neuralmind" / "memory.db").exists()


def test_scan_opt_out_imports_nothing(repo, capsys, monkeypatch):
    monkeypatch.setenv("NEURALMIND_DECISION_SCAN", "0")
    assert "skipped" in _scan(repo, capsys)
    assert not (repo / ".neuralmind" / "memory.db").exists()


def test_scan_exits_cleanly_when_the_store_is_refused(repo, capsys, monkeypatch):
    # A storage policy that refuses the disk must not fail the commit the
    # post-commit hook follows: scan always exits 0.
    import neuralmind.cli as cli
    from neuralmind.storage_guard import StorageNotVerifiedError

    def refuse(_path):
        raise StorageNotVerifiedError("encrypted storage required")

    monkeypatch.setattr(cli, "_get_decisions_store", refuse)
    payload = json.loads(_scan(repo, capsys, "--json"))
    assert payload == {"commit": "", "stale": [], "imported": []}
