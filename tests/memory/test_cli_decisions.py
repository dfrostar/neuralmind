"""CLI-level regression tests for ``neuralmind decisions`` — v4.2.1 remediation R1/R2.

Why this file exists: the v4.1/v4.2 shipments passed 74/74 unit tests while
two headline CLI defects shipped —

- ``decisions query`` crashed on **every** result: cli.py read ``d.files``
  while the model field is ``files_affected`` (AttributeError).
- ``decisions audit`` printed "No decisions recorded yet." on a healthy store,
  because ``store.audit()`` deliberately returns only stale+orphaned entries
  (the maintenance view) while the CLI help promises "List all decisions".

These tests drive the **real parser** (``build_parser()``) and the command
functions end to end, so argparse wiring and rendering are both covered.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from neuralmind.cli import build_parser
from neuralmind.memory.store import STALE_DAYS, DecisionStore


@pytest.fixture
def parser():
    return build_parser()


@pytest.fixture
def project(tmp_path):
    return tmp_path


def _run(parser, argv, capsys):
    args = parser.parse_args(argv)
    args.func(args)
    return capsys.readouterr().out


def _record(store: DecisionStore, **overrides):
    kwargs = {
        "title": "Syringe units model",
        "rationale": "Vial powder mg + reconstitution volume mL -> dose in mcg; draw in U-100 units.",
        "commit_sha": "a" * 40,
        "files_affected": ["lib/utils/dose_conversion.dart"],
    }
    kwargs.update(overrides)
    return store.record(**kwargs)


# ------------------------------------------------------------------ #
# R1 — query renders results (regression: AttributeError on d.files)
# ------------------------------------------------------------------ #


def test_query_renders_result_with_files(parser, project, capsys):
    _record(DecisionStore(str(project)))
    out = _run(parser, ["decisions", "query", "syringe", str(project)], capsys)
    assert "Syringe units model" in out
    assert "lib/utils/dose_conversion.dart" in out


def test_query_renders_result_without_files(parser, project, capsys):
    """The exact v4.2.0 crash case: a decision recorded without --files."""
    _record(DecisionStore(str(project)), files_affected=[])
    out = _run(parser, ["decisions", "query", "syringe", str(project)], capsys)
    assert "Syringe units model" in out


def test_query_no_results_message(parser, project, capsys):
    out = _run(parser, ["decisions", "query", "zebra nothing matches", str(project)], capsys)
    assert "No decisions found for: zebra nothing matches" in out


def test_query_json_includes_files_affected(parser, project, capsys):
    _record(DecisionStore(str(project)))
    out = _run(parser, ["decisions", "query", "syringe", str(project), "--json"], capsys)
    payload = json.loads(out)
    assert payload[0]["files_affected"] == ["lib/utils/dose_conversion.dart"]


# ------------------------------------------------------------------ #
# R2 — audit lists healthy decisions by default (was: "none recorded")
# ------------------------------------------------------------------ #


def test_audit_lists_recorded_decision(parser, project, capsys):
    _record(DecisionStore(str(project)))
    out = _run(parser, ["decisions", "audit", str(project)], capsys)
    assert "Syringe units model" in out
    assert "1 entry" in out


def test_audit_empty_project_message(parser, project, capsys):
    out = _run(parser, ["decisions", "audit", str(project)], capsys)
    assert "No decisions recorded yet." in out


def test_audit_stale_filter_excludes_healthy(parser, project, capsys):
    _record(DecisionStore(str(project)))
    out = _run(parser, ["decisions", "audit", str(project), "--stale"], capsys)
    assert "Syringe units model" not in out
    assert "No stale decisions." in out


def test_audit_stale_filter_includes_old_decision(parser, project, capsys):
    old = datetime.now(timezone.utc) - timedelta(days=STALE_DAYS + 1)
    _record(DecisionStore(str(project)), created_at=old, updated_at=old)
    out = _run(parser, ["decisions", "audit", str(project), "--stale"], capsys)
    assert "Syringe units model" in out


def test_audit_default_view_still_shows_old_decision(parser, project, capsys):
    """Default view is 'all', so a stale decision appears there too."""
    old = datetime.now(timezone.utc) - timedelta(days=STALE_DAYS + 1)
    _record(DecisionStore(str(project)), created_at=old, updated_at=old)
    out = _run(parser, ["decisions", "audit", str(project)], capsys)
    assert "Syringe units model" in out


def test_audit_json_shape(parser, project, capsys):
    _record(DecisionStore(str(project)))
    out = _run(parser, ["decisions", "audit", str(project), "--format", "json"], capsys)
    payload = json.loads(out)
    assert payload[0]["title"] == "Syringe units model"
    assert payload[0]["files_affected"] == ["lib/utils/dose_conversion.dart"]


# ------------------------------------------------------------------ #
# Round-trip: record via CLI -> appears in both views
# ------------------------------------------------------------------ #


def test_record_then_query_and_audit_agree(parser, project, capsys):
    _run(
        parser,
        [
            "decisions",
            "record",
            str(project),
            "--title",
            "U-100 default",
            "--rationale",
            "U-100 syringes are the default; U-40 supported per vial.",
            "--commit",
            "b" * 40,
            "--files",
            "lib/utils/dose_conversion.dart",
        ],
        capsys,
    )
    query_out = _run(parser, ["decisions", "query", "U-100", str(project)], capsys)
    audit_out = _run(parser, ["decisions", "audit", str(project)], capsys)
    assert "U-100 default" in query_out
    assert "U-100 default" in audit_out
    assert "lib/utils/dose_conversion.dart" in audit_out


# ------------------------------------------------------------------ #
# decisions scan — the post-commit invalidation entry point
# ------------------------------------------------------------------ #


def _git(repo, *args):
    import subprocess

    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test")
    (tmp_path / "lib").mkdir()
    (tmp_path / "lib" / "dose.dart").write_text("const u = 100;\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "initial")
    return tmp_path


def _change_and_commit(repo):
    (repo / "lib" / "dose.dart").write_text("const u = 40; // changed\n")
    _git(repo, "commit", "-qam", "switch to U-40")


def test_scan_marks_touched_decision_stale(parser, repo, capsys, monkeypatch):
    monkeypatch.delenv("NEURALMIND_DECISION_SCAN", raising=False)
    store = DecisionStore(str(repo))
    rec = _record(store, files_affected=["lib/dose.dart"])
    _change_and_commit(repo)
    out = _run(parser, ["decisions", "scan", str(repo)], capsys)
    assert "1 decision(s) marked STALE" in out
    assert "Syringe units model" in out
    assert rec.id in out  # the full id, so `decisions restore <id>` works
    assert store.get(rec.id).status == "STALE"


def test_scan_json(parser, repo, capsys, monkeypatch):
    monkeypatch.delenv("NEURALMIND_DECISION_SCAN", raising=False)
    rec = _record(DecisionStore(str(repo)), files_affected=["lib/dose.dart"])
    _change_and_commit(repo)
    payload = json.loads(_run(parser, ["decisions", "scan", str(repo), "--json"], capsys))
    assert payload["commit"] == _git(repo, "rev-parse", "HEAD")
    assert [s["id"] for s in payload["stale"]] == [rec.id]
    assert "changed lib/dose.dart" in payload["stale"][0]["reason"]


def test_scan_quiet_prints_nothing_when_nothing_went_stale(parser, repo, capsys, monkeypatch):
    monkeypatch.delenv("NEURALMIND_DECISION_SCAN", raising=False)
    _record(DecisionStore(str(repo)), files_affected=["lib/other.dart"])
    _change_and_commit(repo)
    assert _run(parser, ["decisions", "scan", str(repo), "--quiet"], capsys) == ""


def test_scan_never_creates_a_decision_store(parser, repo, capsys, monkeypatch):
    monkeypatch.delenv("NEURALMIND_DECISION_SCAN", raising=False)
    _change_and_commit(repo)
    assert _run(parser, ["decisions", "scan", str(repo), "--quiet"], capsys) == ""
    assert not (repo / ".neuralmind" / "memory.db").exists()


def test_scan_opt_out(parser, repo, capsys, monkeypatch):
    monkeypatch.setenv("NEURALMIND_DECISION_SCAN", "0")
    store = DecisionStore(str(repo))
    rec = _record(store, files_affected=["lib/dose.dart"])
    _change_and_commit(repo)
    out = _run(parser, ["decisions", "scan", str(repo)], capsys)
    assert "skipped" in out
    assert store.get(rec.id).status == "ACTIVE"


def test_scan_outside_a_git_repo_is_a_noop(parser, project, capsys, monkeypatch):
    monkeypatch.delenv("NEURALMIND_DECISION_SCAN", raising=False)
    rec = _record(DecisionStore(str(project)))
    out = _run(parser, ["decisions", "scan", str(project)], capsys)
    assert "not a git repository" in out
    assert DecisionStore(str(project)).get(rec.id).status == "ACTIVE"


def test_init_hook_post_commit_runs_the_scan(tmp_path, capsys):
    from unittest.mock import MagicMock

    from neuralmind.cli import cmd_init_hook

    (tmp_path / ".git" / "hooks").mkdir(parents=True)
    args = MagicMock()
    args.project_path = str(tmp_path)
    args.no_drift = True
    cmd_init_hook(args)
    hook = (tmp_path / ".git" / "hooks" / "post-commit").read_text()
    assert "neuralmind decisions scan . --quiet || true" in hook
    # The scan runs before the (slower) rebuild, inside the managed block.
    assert hook.index("decisions scan") < hook.index("neuralmind build .")
    assert hook.index("neuralmind-hook-start") < hook.index("decisions scan")


def _init_hook(project, no_drift=False):
    from unittest.mock import MagicMock

    from neuralmind.cli import cmd_init_hook

    args = MagicMock()
    args.project_path = str(project)
    args.no_drift = no_drift
    args.strict = False
    cmd_init_hook(args)


def test_init_hook_for_a_project_in_a_subdirectory(repo, capsys):
    """Git runs hooks from the repository root: name the project from there."""
    project = repo / "services" / "api"
    project.mkdir(parents=True)
    _init_hook(project)
    post_commit = (repo / ".git" / "hooks" / "post-commit").read_text()
    assert "neuralmind decisions scan services/api --quiet || true" in post_commit
    assert "neuralmind build services/api" in post_commit
    pre_commit = (repo / ".git" / "hooks" / "pre-commit").read_text()
    assert "neuralmind drift services/api --staged" in pre_commit
    assert "For the project at services" in capsys.readouterr().out


def test_init_hook_quotes_a_path_with_spaces(repo):
    project = repo / "my service"
    project.mkdir()
    _init_hook(project, no_drift=True)
    post_commit = (repo / ".git" / "hooks" / "post-commit").read_text()
    assert "neuralmind decisions scan 'my service' --quiet || true" in post_commit


def test_init_hook_in_a_linked_worktree(repo, tmp_path):
    """A worktree's `.git` is a file; its hooks are the repository's."""
    worktree = tmp_path / "wt"
    _git(repo, "worktree", "add", "-q", str(worktree))
    _init_hook(worktree, no_drift=True)
    post_commit = (repo / ".git" / "hooks" / "post-commit").read_text()
    assert "neuralmind decisions scan . --quiet || true" in post_commit


# ------------------------------------------------------------------ #
# --status filter (side finding 1: "all" and lowercase matched nothing)
# ------------------------------------------------------------------ #


def _record_each_status(store: DecisionStore):
    active = _record(store, title="Syringe units model active")
    gone = _record(store, title="Syringe units model retired")
    store.invalidate(gone.id, reason="superseded")
    return active, gone


@pytest.mark.parametrize("word", ["all", "ALL", "All"])
def test_query_status_all_any_case(parser, project, capsys, word):
    active, gone = _record_each_status(DecisionStore(str(project)))
    out = _run(
        parser, ["decisions", "query", "Syringe", str(project), "--status", word, "--json"], capsys
    )
    assert {d["id"] for d in json.loads(out)} == {active.id, gone.id}


def test_query_status_invalidated_lowercase(parser, project, capsys):
    _, gone = _record_each_status(DecisionStore(str(project)))
    out = _run(
        parser,
        ["decisions", "query", "Syringe", str(project), "--status", "invalidated", "--json"],
        capsys,
    )
    assert [d["id"] for d in json.loads(out)] == [gone.id]


def test_query_status_unknown_is_a_usage_error(parser, project, capsys):
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["decisions", "query", "Syringe", str(project), "--status", "archived"])
    assert exc.value.code == 2
    assert "invalid choice" in capsys.readouterr().err


# ------------------------------------------------------------------ #
# restore of an unknown id (was a KeyError traceback)
# ------------------------------------------------------------------ #


def test_restore_unknown_id_is_an_error_not_a_traceback(parser, project, capsys):
    _record(DecisionStore(str(project)))
    with pytest.raises(SystemExit) as exc:
        _run(
            parser,
            ["decisions", "restore", "no-such-id", str(project), "--commit", "b" * 40],
            capsys,
        )
    assert exc.value.code == 1
    assert "Decision not found: no-such-id" in capsys.readouterr().err


def test_restore_known_id_still_reanchors(parser, project, capsys):
    store = DecisionStore(str(project))
    rec = _record(store)
    store.mark_stale(rec.id, reason="files changed")
    out = _run(parser, ["decisions", "restore", rec.id, str(project), "--commit", "b" * 40], capsys)
    assert f"Restored decision: {rec.id}" in out
    got = store.get(rec.id)
    assert got.status == "ACTIVE"
    assert got.commit_sha == "b" * 40


def test_restore_db_error_is_an_error(parser, project, capsys, monkeypatch):
    # The store raises on a failed update (tests/memory/test_store.py drives
    # a real one); here, the CLI must report it rather than print "Restored".
    import sqlite3

    store = DecisionStore(str(project))
    rec = _record(store)
    store.mark_stale(rec.id, reason="files changed")

    def locked(self, decision_id, new_commit_sha):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(DecisionStore, "restore", locked)
    with pytest.raises(SystemExit) as exc:
        _run(parser, ["decisions", "restore", rec.id, str(project), "--commit", "b" * 40], capsys)
    assert exc.value.code == 1
    captured = capsys.readouterr()
    assert f"Could not restore decision {rec.id}" in captured.err
    assert "Restored decision" not in captured.out


# ------------------------------------------------------------------ #
# invalidate reports failure (an unknown id or a DB error said "Invalidated")
# ------------------------------------------------------------------ #


def test_invalidate_unknown_id_is_an_error(parser, project, capsys):
    _record(DecisionStore(str(project)))
    with pytest.raises(SystemExit) as exc:
        _run(parser, ["decisions", "invalidate", "no-such-id", str(project)], capsys)
    assert exc.value.code == 1
    captured = capsys.readouterr()
    assert "Decision not found: no-such-id" in captured.err
    assert "Invalidated decision" not in captured.out


def test_invalidate_db_error_is_an_error(parser, project, capsys):
    import sqlite3

    store = DecisionStore(str(project))
    rec = _record(store)
    with sqlite3.connect(store.db_path) as conn:
        conn.execute("UPDATE decisions SET evidence = '{bad' WHERE id = ?", (rec.id,))
    with pytest.raises(SystemExit) as exc:
        _run(parser, ["decisions", "invalidate", rec.id, str(project)], capsys)
    assert exc.value.code == 1
    captured = capsys.readouterr()
    assert f"Could not invalidate decision {rec.id}" in captured.err
    assert "Invalidated decision" not in captured.out


def test_invalidate_known_id_still_succeeds(parser, project, capsys):
    store = DecisionStore(str(project))
    rec = _record(store)
    out = _run(
        parser, ["decisions", "invalidate", rec.id, str(project), "--reason", "superseded"], capsys
    )
    assert f"Invalidated decision: {rec.id}" in out
    assert store.get(rec.id).status == "INVALIDATED"


# ------------------------------------------------------------------ #
# record --confidence is 0-1 (7 was accepted and stored as 1.0)
# ------------------------------------------------------------------ #


def _record_argv(project, confidence):
    return [
        "decisions",
        "record",
        "--title",
        "t",
        "--rationale",
        "r",
        "--commit",
        "a" * 40,
        "--confidence",
        confidence,
        str(project),
    ]


@pytest.mark.parametrize("bad", ["7", "-0.1", "1.5", "nan", "inf", "abc"])
def test_record_rejects_confidence_outside_0_to_1(parser, project, capsys, bad):
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(_record_argv(project, bad))
    assert exc.value.code == 2
    assert "confidence must be a number from 0 to 1" in capsys.readouterr().err
    assert not (project / ".neuralmind").exists()  # nothing recorded


@pytest.mark.parametrize("good, stored", [("0", 0.0), ("0.4", 0.4), ("1", 1.0)])
def test_record_accepts_confidence_in_range(parser, project, capsys, good, stored):
    out = _run(parser, _record_argv(project, good), capsys)
    assert "Recorded decision" in out
    (decision,) = DecisionStore(str(project)).list_all()
    assert decision.confidence == stored
