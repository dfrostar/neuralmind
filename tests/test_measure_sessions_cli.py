"""`neuralmind measure sessions`: the table, `--json`, `--rows` and exit 2, on synthetic sessions.

The fixtures are test_exploration_share's, whose numbers are exact under the
characters / 4 counting `--estimate` selects. Both fixtures sit in the past
(the Hermes sessions at epoch 1000-1990, the transcript on 2026-10-10), so the
window is made wide enough to hold them.
"""

from __future__ import annotations

import ast
import json
import sqlite3
import sys
from pathlib import Path

import pytest

from neuralmind import cli
from neuralmind.measure import claude_code, report
from neuralmind.measure.tokens import Tokenizer
from tests.test_exploration_share import HERMES_SCHEMA, _claude_transcript, _hermes_db

WIDE = ["--since-days", "100000", "--estimate"]
ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def home(tmp_path, monkeypatch):
    """A HOME with neither agent's store in it, and no env pointing at the real ones."""
    h = tmp_path / "home"
    h.mkdir()
    monkeypatch.setenv("HOME", str(h))
    monkeypatch.setenv("USERPROFILE", str(h))
    monkeypatch.setenv("HERMES_HOME", str(h / ".hermes"))
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    return h


@pytest.fixture
def stores(tmp_path):
    """A Claude Code transcript (one session) and a Hermes state.db (three), outside HOME."""
    proj = tmp_path / "claude" / "-Users-someone-secret-project"
    proj.mkdir(parents=True)
    _claude_transcript(proj / "cc1.jsonl", billed=(400, 426, 400))
    db = tmp_path / "hermes" / "state.db"
    db.parent.mkdir()
    _hermes_db(db)
    return tmp_path / "claude", db


def run(monkeypatch, capsys, *argv: str) -> tuple[int, str, str]:
    monkeypatch.setattr(sys, "argv", ["neuralmind", "measure", "sessions", *argv])
    try:
        cli.main()
        code = 0
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else 1
    out = capsys.readouterr()
    return code, out.out, out.err


def test_prints_both_shares_and_the_reading(home, stores, monkeypatch, capsys):
    claude_root, db = stores
    code, out, err = run(
        monkeypatch, capsys, *WIDE, "--claude-root", str(claude_root), "--hermes-db", str(db)
    )
    assert code == 0, err
    assert "Exploration share of the token bill" in out
    assert "Claude Code: read; Hermes: read" in out
    # one row per agent / source group, with the session counts of the fixtures
    assert "claude-code / interactive" in out and "hermes / interactive" in out
    assert "Exploration of context" in out and "of billed prompt" in out
    assert "Pre-registered reading (interactive sessions" in out
    assert "claude-code/interactive (1 session): " in out
    assert "hermes/interactive (3 sessions): " in out
    assert "chars/4" in out, "the tokenizer is named, estimate or not"
    assert "EXPLORATION-SHARE-SPEC.md" in out


def test_stdout_holds_aggregates_only(home, stores, tmp_path, monkeypatch, capsys):
    claude_root, db = stores
    for extra in ([], ["--json"]):
        code, out, _ = run(
            monkeypatch,
            capsys,
            *WIDE,
            "--claude-root",
            str(claude_root),
            "--hermes-db",
            str(db),
            *extra,
        )
        assert code == 0
        for private in (
            str(tmp_path),  # any path
            "someone-secret-project",  # a project name
            "cc1",  # a session id
            "fix the bug",  # a prompt
            "claude-x",  # a model
        ):
            assert private not in out, f"{private!r} leaked to stdout ({extra})"


def test_json_is_the_aggregate_plus_window_and_sources(home, stores, monkeypatch, capsys):
    claude_root, db = stores
    code, out, _ = run(
        monkeypatch,
        capsys,
        *WIDE,
        "--claude-root",
        str(claude_root),
        "--hermes-db",
        str(db),
        "--json",
    )
    assert code == 0
    data = json.loads(out)
    assert data["sources"] == {"claude-code": "read", "hermes": "read"}
    assert data["tokenizer"] == "chars/4" and data["window"]["until"] > data["window"]["since"]
    assert data["n_sessions"] == 4
    cc = data["groups"]["claude-code/interactive"]
    assert cc["sessions"] == 1 and cc["calls"] == 3 and cc["prompt_tokens_billed"] == 1226
    # the transcript fixture: 25 exploration tokens present at call 2 (test_exploration_share)
    assert cc["billed_tokens"]["exploration"] == 25
    assert cc["exploration_share_billed"] == pytest.approx(25 / cc["context_tokens_est"])
    assert cc["exploration_share_of_prompt"] == pytest.approx(25 / 1226)
    assert "under 10%" in data["reading"]["claude-code/interactive"]
    # the same numbers the evals report would compute from the same collectors
    rows = claude_code.collect(claude_root, 0, 2_000_000_000, Tokenizer(force_estimate=True))
    assert data["groups"]["claude-code/interactive"] == (
        report.aggregate([r.to_json() for r in rows])["groups"]["claude-code/interactive"]
    )


def test_rows_are_written_where_asked_and_never_printed(
    home, stores, tmp_path, monkeypatch, capsys
):
    claude_root, db = stores
    rows_path = tmp_path / "out" / "rows.jsonl"
    code, out, err = run(
        monkeypatch,
        capsys,
        *WIDE,
        "--claude-root",
        str(claude_root),
        "--hermes-db",
        str(db),
        "--rows",
        str(rows_path),
    )
    assert code == 0
    rows = [json.loads(line) for line in rows_path.read_text(encoding="utf-8").splitlines()]
    assert sorted(r["session_id"] for r in rows) == ["cc1", "s1", "s2", "s3"]
    assert str(rows_path) not in out and str(rows_path) in err
    # a second run replaces the file rather than appending to it
    run(monkeypatch, capsys, *WIDE, "--hermes-db", str(db), "--rows", str(rows_path))
    assert len(rows_path.read_text(encoding="utf-8").splitlines()) == 3


def test_exit_1_when_the_rows_file_cannot_be_written(home, stores, tmp_path, monkeypatch, capsys):
    claude_root, db = stores
    blocker = tmp_path / "a-file"
    blocker.write_text("x", encoding="utf-8")
    code, out, err = run(
        monkeypatch,
        capsys,
        *WIDE,
        "--hermes-db",
        str(db),
        "--rows",
        str(blocker / "rows.jsonl"),  # its parent is a file
    )
    assert code == 1 and out == ""
    assert "--rows could not be written" in err and str(tmp_path) not in err.split("(")[-1]


def test_finds_both_stores_without_flags(home, stores, monkeypatch, capsys):
    claude_root, db = stores
    (home / ".claude").mkdir()
    (claude_root).rename(home / ".claude" / "projects")
    (home / ".hermes").mkdir()
    db.rename(home / ".hermes" / "state.db")
    code, out, err = run(monkeypatch, capsys, *WIDE)
    assert code == 0, err
    assert "Claude Code: read; Hermes: read" in out


def test_claude_config_dir_moves_the_default(home, stores, tmp_path, monkeypatch, capsys):
    claude_root, _ = stores
    config = tmp_path / "cfg"
    config.mkdir()
    claude_root.rename(config / "projects")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(config))
    code, out, _ = run(monkeypatch, capsys, *WIDE)
    assert code == 0 and "Claude Code: read; Hermes: not found" in out


def test_exit_2_when_no_sessions_in_the_window(home, stores, monkeypatch, capsys):
    claude_root, db = stores
    # the fixtures are older than a day: both stores exist, neither holds a session in the window
    code, out, err = run(
        monkeypatch,
        capsys,
        "--since-days",
        "1",
        "--estimate",
        "--claude-root",
        str(claude_root),
        "--hermes-db",
        str(db),
    )
    assert code == 2 and out == ""
    assert "no sessions found in the last 1 days" in err
    assert "Claude Code: read; Hermes: read" in err


def test_exit_2_when_neither_agent_is_installed(home, monkeypatch, capsys):
    code, out, err = run(monkeypatch, capsys, *WIDE)
    assert code == 2 and out == ""
    assert "Claude Code: not found; Hermes: not found" in err


@pytest.mark.parametrize(
    "argv, message",
    [
        (["--claude-root", "{tmp}/missing"], "--claude-root is not a directory"),
        (["--hermes-db", "{tmp}/missing.db"], "--hermes-db is not a file"),
        (["--since-days", "0"], "must be above 0"),
        (["--since-days", "soon"], "invalid number"),
    ],
)
def test_exit_2_on_arguments_that_cannot_be_read(
    home, tmp_path, monkeypatch, capsys, argv, message
):
    code, out, err = run(monkeypatch, capsys, *[a.format(tmp=tmp_path) for a in argv])
    assert code == 2 and out == ""
    assert message in err


def test_an_unreadable_hermes_db_does_not_stop_claude_code(
    home, stores, tmp_path, monkeypatch, capsys
):
    claude_root, _ = stores
    bad = tmp_path / "bad.db"
    bad.write_bytes(b"this is not a database" * 100)
    code, out, err = run(
        monkeypatch, capsys, *WIDE, "--claude-root", str(claude_root), "--hermes-db", str(bad)
    )
    assert code == 0
    assert "Hermes state.db could not be read" in err
    assert "Claude Code: read; Hermes: unreadable" in out
    assert str(tmp_path) not in out


def test_a_hermes_db_with_another_schema_is_unreadable_not_a_crash(
    home, tmp_path, monkeypatch, capsys
):
    db = tmp_path / "state.db"
    con = sqlite3.connect(db)
    con.executescript(HERMES_SCHEMA.replace("api_content text", "other text"))
    # the messages query only runs for a session that exists
    con.execute("insert into sessions values ('s1','cli','m',1000,1100,'',1,1,0,0)")
    con.commit()
    con.close()
    code, out, err = run(monkeypatch, capsys, *WIDE, "--hermes-db", str(db))
    assert code == 2 and "could not be read" in err and "no such column" in err


def test_one_unreadable_transcript_is_skipped_and_counted(home, stores, monkeypatch, capsys):
    claude_root, _ = stores
    bad = claude_root / "-Users-someone-secret-project" / "broken.jsonl"
    # valid JSON, wrong shape: the collector would raise on `message.get`
    bad.write_text(
        json.dumps({"type": "user", "timestamp": "2026-10-10T10:00:00Z", "message": "oops"}) + "\n",
        encoding="utf-8",
    )
    code, out, err = run(monkeypatch, capsys, *WIDE, "--claude-root", str(claude_root), "-j")
    assert code == 0
    assert "Skipped 1 Claude Code transcript(s) that could not be read" in err
    assert json.loads(out)["n_sessions"] == 1, "the readable session is still measured"


def test_measure_without_a_subcommand_is_a_usage_error(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["neuralmind", "measure"])
    with pytest.raises(SystemExit) as e:
        cli.main()
    assert e.value.code == 2


def test_the_product_package_does_not_import_evals():
    """evals/ isn't shipped, so nothing under neuralmind/ may depend on it."""
    for path in (ROOT / "neuralmind" / "measure").glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names = (
                [a.name for a in node.names]
                if isinstance(node, ast.Import)
                else [node.module or ""] if isinstance(node, ast.ImportFrom) else []
            )
            assert not any(n == "evals" or n.startswith("evals.") for n in names), path.name
