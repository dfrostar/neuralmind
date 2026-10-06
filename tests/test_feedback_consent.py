"""`neuralmind feedback good/bad` names memory consent when that is why nothing was recorded.

Regression: with query memory off (no consent, consent declined, or
NEURALMIND_MEMORY=0) no query is ever written to recent_queries.jsonl, yet
feedback said "No recent queries recorded. Run `neuralmind query ...` first."
— advice that can't work, since the next query isn't recorded either.
"""

from __future__ import annotations

import pytest

from neuralmind import memory
from neuralmind.cli import build_parser


@pytest.fixture
def home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.delenv("NEURALMIND_MEMORY", raising=False)
    return home


@pytest.fixture
def project(tmp_path):
    p = tmp_path / "proj"
    p.mkdir()
    return p


def _feedback(verdict, project, capsys):
    args = build_parser().parse_args(["feedback", verdict, str(project)])
    with pytest.raises(SystemExit) as exc:
        args.func(args)
    assert exc.value.code == 1
    return capsys.readouterr().err


@pytest.mark.parametrize("verdict", ["good", "bad"])
def test_no_consent_yet_says_memory_is_off(verdict, home, project, capsys):
    err = _feedback(verdict, project, capsys)
    assert "query memory is off" in err
    assert "hasn't been enabled" in err
    assert str(memory.consent_file()) in err
    assert "first." not in err  # not the "run a query first" advice


@pytest.mark.parametrize("verdict", ["good", "bad"])
def test_declined_consent_says_how_to_turn_it_on(verdict, home, project, capsys):
    memory.write_consent_sentinel(False)
    err = _feedback(verdict, project, capsys)
    assert "query memory is off" in err
    assert "declined" in err
    assert '"memory_logging_enabled" to true' in err
    assert str(memory.consent_file()) in err


def test_env_switch_off_names_the_variable(home, project, capsys, monkeypatch):
    memory.write_consent_sentinel(True)
    monkeypatch.setenv("NEURALMIND_MEMORY", "0")
    err = _feedback("good", project, capsys)
    assert "NEURALMIND_MEMORY=0" in err
    assert "unset NEURALMIND_MEMORY" in err
    assert "declined" not in err


def test_memory_on_but_no_queries_keeps_the_run_a_query_hint(home, project, capsys):
    memory.write_consent_sentinel(True)
    err = _feedback("good", project, capsys)
    assert "No recent queries recorded" in err
    assert "query memory is off" not in err


def _write_recorded_query(project, question="where is auth handled?"):
    """A recent-queries record left from when memory was on, plus a synapse store."""
    import json

    from neuralmind.synapses import SynapseStore, default_db_path

    state = project / ".neuralmind"
    state.mkdir(exist_ok=True)
    record = {
        "ts": "2026-01-02T03:04:05+00:00",
        "question": question,
        "top_hits": [{"id": "auth_login"}, {"id": "auth_session"}, {"id": "auth_token"}],
    }
    (state / "recent_queries.jsonl").write_text(json.dumps(record) + "\n", encoding="utf-8")
    db = default_db_path(project)
    SynapseStore(db)  # creates the schema
    return db


def _edge_count(db):
    import sqlite3

    with sqlite3.connect(db) as conn:
        return conn.execute("SELECT COUNT(*) FROM synapses").fetchone()[0]


@pytest.mark.parametrize("verdict", ["good", "bad"])
def test_memory_off_does_not_adjust_a_query_recorded_before(verdict, home, project, capsys):
    # Regression: feedback adjusted the newest record even though queries
    # asked since memory went off were never recorded — so "the last query"
    # was really some older one.
    db = _write_recorded_query(project)
    err = _feedback(verdict, project, capsys)
    assert "not applied" in err
    assert "query memory is off" in err
    assert "where is auth handled?" in err
    assert "2026-01-02T03:04:05+00:00" in err
    assert str(memory.consent_file()) in err
    assert _edge_count(db) == 0


def test_memory_off_by_env_does_not_adjust_a_recorded_query(home, project, capsys, monkeypatch):
    memory.write_consent_sentinel(True)
    monkeypatch.setenv("NEURALMIND_MEMORY", "0")
    db = _write_recorded_query(project)
    err = _feedback("good", project, capsys)
    assert "not applied" in err
    assert "unset NEURALMIND_MEMORY" in err
    assert _edge_count(db) == 0


def test_memory_on_adjusts_the_recorded_query(home, project, capsys):
    memory.write_consent_sentinel(True)
    db = _write_recorded_query(project)
    args = build_parser().parse_args(["feedback", "good", str(project)])
    args.func(args)
    assert "Boosted 3 edges" in capsys.readouterr().out
    assert _edge_count(db) == 3
