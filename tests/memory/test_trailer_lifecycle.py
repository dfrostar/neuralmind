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


# --------------------------------------------------------------------------- #
# Imported trailers are judged against their own commit, not the working tree
# --------------------------------------------------------------------------- #


def _status(repo, decision_id):
    return DecisionStore(str(repo)).get(decision_id).status


def test_an_old_trailer_whose_code_changed_since_comes_in_stale(repo, capsys):
    # The trailer's commit is HEAD~1; this commit changes its file again. The
    # first import (here, the one-time scan) must not take today's code as
    # what the decision described.
    _commit(repo, "src/uploader.py", "def upload_with_retry():\n    pass\n", "drop retry")
    out = _scan(repo, capsys)
    assert "1 STALE" in out
    record = DecisionStore(str(repo)).get(_trailer_id())
    assert record.status == "STALE"
    assert any("src/uploader.py changed after commit" in e for e in record.evidence)


def test_an_old_trailer_with_unchanged_code_comes_in_active(repo, capsys):
    _commit(repo, "README.md", "readme\n", "docs")
    _scan(repo, capsys)
    assert _status(repo, _trailer_id()) == "ACTIVE"


def test_a_dirty_working_tree_is_not_taken_as_the_decisions_code(repo, capsys):
    # Uncommitted edits at import time, committed later: that commit changes
    # the code the trailer's commit stored, so it marks the decision STALE.
    (repo / "src" / "uploader.py").write_text("def upload_with_retry():\n    pass\n")
    _scan(repo, capsys)
    assert _status(repo, _trailer_id()) == "ACTIVE"
    _git(repo, "commit", "-qam", "drop retry")
    _scan(repo, capsys)
    assert _status(repo, _trailer_id()) == "STALE"


def test_amending_the_trailers_commit_does_not_make_it_stale(repo, capsys):
    _scan(repo, capsys)
    (repo / "src" / "uploader.py").write_text("def upload_with_retry():\n    retry(3)\n")
    _git(repo, "commit", "-q", "-a", "--amend", "--no-edit")
    _scan(repo, capsys)  # what the post-commit hook runs after the amend
    record = DecisionStore(str(repo)).get(_trailer_id())
    assert record.status == "ACTIVE"
    assert record.commit_sha == _git(repo, "rev-parse", "HEAD")  # not the orphaned sha


def test_the_same_rationale_committed_again_reanchors_it(repo, capsys):
    _scan(repo, capsys)
    _commit(
        repo, "src/uploader.py", "def upload_with_retry():\n    retry(5)\n", f"tune\n\n{TRAILER}"
    )
    _scan(repo, capsys)
    record = DecisionStore(str(repo)).get(_trailer_id())
    assert record.status == "ACTIVE"
    assert record.commit_sha == _git(repo, "rev-parse", "HEAD")


def test_reasserting_an_invalidated_trailer_keeps_it_invalidated(repo, capsys):
    _scan(repo, capsys)
    DecisionStore(str(repo)).invalidate(_trailer_id(), reason="reversed")
    _commit(repo, "src/uploader.py", "x = 1\n", f"again\n\n{TRAILER}")
    _scan(repo, capsys)
    assert _status(repo, _trailer_id()) == "INVALIDATED"


def test_a_non_ascii_path_is_stored_as_git_names_it_and_goes_stale(repo, capsys):
    trailer = "Decision: `café_rate` rounds half-even so totals match the ledger."
    _commit(repo, "src/café.py", "def café_rate(): ...\n", f"feat: rates\n\n{trailer}")
    _scan(repo, capsys)
    decision_id = trailer_decision_id(parse_decision(f"x\n\n{trailer}"))
    assert DecisionStore(str(repo)).get(decision_id).files_affected == ["src/café.py"]
    _commit(repo, "src/café.py", "def café_rate(): return 1\n", "change")
    _scan(repo, capsys)
    assert _status(repo, decision_id) == "STALE"


def test_a_trailer_on_a_merge_commit_names_what_the_merge_brought_in(repo, capsys):
    main = _git(repo, "branch", "--show-current")
    _git(repo, "checkout", "-q", "-b", "feature")
    _commit(repo, "src/feature.py", "def feature(): ...\n", "feature work")
    _git(repo, "checkout", "-q", main)
    _commit(repo, "README.md", "readme\n", "docs")  # so the merge isn't a fast-forward
    trailer = "Decision: `feature` ships behind a flag until the migration lands."
    _git(repo, "merge", "-q", "--no-ff", "feature", "-m", f"merge feature\n\n{trailer}")
    _scan(repo, capsys)
    decision_id = trailer_decision_id(parse_decision(f"x\n\n{trailer}"))
    assert DecisionStore(str(repo)).get(decision_id).files_affected == ["src/feature.py"]


def test_scan_json_is_printed_when_the_scan_itself_fails(repo, capsys, monkeypatch):
    from neuralmind.memory import invalidate

    def boom(self):
        raise RuntimeError("git exploded")

    monkeypatch.setattr(invalidate.InvalidationEngine, "scan", boom)
    payload = json.loads(_scan(repo, capsys, "--json"))
    assert payload["imported"] == [_trailer_id()]
    assert payload["stale"] == []


def test_query_prints_the_id_to_invalidate_or_restore(repo, capsys):
    _scan(repo, capsys)
    args = build_parser().parse_args(
        ["decisions", "query", "upload_with_retry uploader", "--status", "ALL", str(repo)]
    )
    args.func(args)
    assert f"ID: {_trailer_id()}" in capsys.readouterr().out


def test_git_output_is_read_as_utf8_whatever_the_locale(monkeypatch):
    # Windows' locale encoding is cp1252: a non-ASCII rationale or path read
    # with it came out garbled (found on the windows-latest CI runner).
    import neuralmind.memory.invalidate as invalidate
    import neuralmind.provenance as provenance

    seen = {}

    def fake_check_output(*args, **kwargs):
        seen["log"] = kwargs.get("encoding")
        return ""

    def fake_run(*args, **kwargs):
        seen["git"] = kwargs.get("encoding")
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "check_output", fake_check_output)
    monkeypatch.setattr(invalidate.subprocess, "run", fake_run)
    provenance.read_git_log(".")
    invalidate.get_changed_files(".")
    assert seen == {"log": "utf-8", "git": "utf-8"}


# --------------------------------------------------------------------------- #
# Review follow-ups (#667): races, Subjects:, pulls and merges
# --------------------------------------------------------------------------- #


def test_mark_stale_never_overrides_an_invalidation():
    # The engine reads a decision, then marks it; an invalidation landing in
    # between must stand (the write checks for ACTIVE in the same UPDATE).
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        store = DecisionStore(tmp)
        rec = store.record(title="t", rationale="r", commit_sha="a" * 40)
        store.invalidate(rec.id, reason="reversed")
        assert store.mark_stale(rec.id, "a commit changed it") is False
        assert store.get(rec.id).status == "INVALIDATED"


def test_reanchoring_never_undoes_an_invalidation_made_meanwhile(repo, capsys):
    _scan(repo, capsys)
    _commit(repo, "src/uploader.py", "x = 2\n", f"again\n\n{TRAILER}")  # HEAD carries it
    store = DecisionStore(str(repo))

    def blobs_reader_that_races(project, files, sha):
        # An explicit invalidation lands while the import is reading git.
        store.invalidate(_trailer_id(), reason="reversed meanwhile")
        from neuralmind.provenance import read_commit_blobs

        return read_commit_blobs(project, files, sha)

    head = _git(repo, "rev-parse", "HEAD")
    import_trailers(
        store, str(repo), harvest(str(repo)), head=head, blobs_reader=blobs_reader_that_races
    )
    record = store.get(_trailer_id())
    assert record.status == "INVALIDATED"
    assert record.commit_sha != head  # not re-anchored either


def test_a_subject_named_only_on_a_subjects_line_is_searchable(repo, capsys):
    message = (
        "feat: auth\n\nDecision: resolve the org id per handler, not in middleware.\n"
        "Subjects: `authMiddleware`"
    )
    _commit(repo, "src/auth.py", "def auth(): ...\n", message)
    _scan(repo, capsys)
    args = build_parser().parse_args(
        ["decisions", "query", "authMiddleware", "--status", "ALL", "--mode", "keyword", str(repo)]
    )
    args.func(args)
    out = capsys.readouterr().out
    assert "subjects: authMiddleware" in out
    assert "ID: " in out


def test_a_subject_inside_a_longer_identifier_is_still_searchable(repo, capsys):
    # Keyword search matches word prefixes: `legacyAuthMiddleware` doesn't
    # name `authMiddleware`, so the subject still goes into the title.
    message = (
        "feat: auth\n\nDecision: keep legacyAuthMiddleware in front of SSO.\n"
        "Subjects: `authMiddleware`"
    )
    _commit(repo, "src/auth.py", "def auth(): ...\n", message)
    _scan(repo, capsys)
    args = build_parser().parse_args(
        ["decisions", "query", "authMiddleware", "--status", "ALL", "--mode", "keyword", str(repo)]
    )
    args.func(args)
    out = capsys.readouterr().out
    assert "subjects: authMiddleware" in out
    assert "ID: " in out


def test_a_pull_that_changes_a_decisions_code_marks_it_stale(repo, capsys):
    _scan(repo, capsys)  # imports the trailer, ACTIVE
    main = _git(repo, "branch", "--show-current")
    _git(repo, "checkout", "-q", "-b", "upstream")
    _commit(repo, "src/uploader.py", "def upload_with_retry():\n    pass\n", "drop retry")
    _commit(repo, "README.md", "readme\n", "docs")  # the decision's file isn't in HEAD's diff
    _git(repo, "checkout", "-q", main)
    _git(repo, "merge", "-q", "--ff-only", "upstream")  # what a pull does; sets ORIG_HEAD
    assert "No recorded decisions affected by commit" in _scan(repo, capsys)  # HEAD only: missed
    out = _scan(repo, capsys, "--since", "ORIG_HEAD")
    assert "1 decision(s) marked STALE by commits" in out
    assert DecisionStore(str(repo)).get(_trailer_id()).status == "STALE"


def test_scan_since_an_unknown_rev_is_skipped(repo, capsys):
    out = _scan(repo, capsys, "--since", "no-such-rev")
    assert "can't resolve" in out


def test_a_since_rev_that_looks_like_an_option_never_reaches_git():
    from neuralmind.memory import invalidate

    assert invalidate.resolve_commit(".", "--output=/tmp/x") == ""
    assert invalidate.resolve_commit(".", "") == ""
