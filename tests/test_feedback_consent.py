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
