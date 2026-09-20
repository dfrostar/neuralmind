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
            "decisions", "record", str(project),
            "--title", "U-100 default",
            "--rationale", "U-100 syringes are the default; U-40 supported per vial.",
            "--commit", "b" * 40,
            "--files", "lib/utils/dose_conversion.dart",
        ],
        capsys,
    )
    query_out = _run(parser, ["decisions", "query", "U-100", str(project)], capsys)
    audit_out = _run(parser, ["decisions", "audit", str(project)], capsys)
    assert "U-100 default" in query_out
    assert "U-100 default" in audit_out
    assert "lib/utils/dose_conversion.dart" in audit_out
