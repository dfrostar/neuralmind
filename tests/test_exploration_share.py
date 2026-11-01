"""Exploration-share collectors (stdlib only; tiktoken is bypassed with chars/4).

The presence model: a message is paid for by every API call after it until a
compaction drops it, or until the context size the provider billed for a call
says it must have been trimmed (oldest trimmable messages first). With chars/4
counting, a 40-character tool result is 10 tokens, so the numbers below are
exact.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from evals.exploration_share import claude_code, hermes_db, report
from evals.exploration_share.__main__ import _parse, main
from evals.exploration_share.classify import (
    EDIT,
    EXPLORATION,
    OTHER,
    SHELL,
    WEB,
    categorize_claude,
    categorize_hermes,
    shell_is_readonly,
)
from evals.exploration_share.rows import BLOCK
from evals.exploration_share.tokens import Tokenizer

TOK = Tokenizer(force_estimate=True)


@pytest.mark.parametrize(
    "command, readonly",
    [
        ("cat foo.py", True),
        ("cd /repo && grep -rn foo src | head -20", True),
        ("git log --oneline -5", True),
        ("git commit -m x", False),
        ("sed -n 1,20p a.py", True),
        ("sed -i s/a/b/ a.py", False),
        ("ls > files.txt", False),
        ("ls 2>errors.log", False),
        ("pytest tests/ 2>&1 | tail -5", False),
        ("pip install tiktoken", False),
        ("echo hi > /dev/null", True),
        ("FOO=1 rg pattern .", True),
        ("", False),
        # operators inside quotes belong to the word
        ("rg 'foo|bar' src", True),
        ("git log --format='%h;%s' -3", True),
        ('grep -r "a && b" .', True),
        ("cat a.py 2>&1", True),
        ("rg -n 'x' . 2>/dev/null | head", True),
        # an unquoted newline separates stages
        ("cat a.py\npytest", False),
        ("ls\nwc -l < a.py", True),
        ("echo 'unbalanced", False),
        # git subcommands that read in one form and write in another
        ("git branch -a", True),
        ("git branch feature", False),
        ("git tag -l", True),
        ("git tag v1.0", False),
        ("git worktree list", True),
        ("git worktree add ../w", False),
        ("git remote -v", True),
        ("git remote add o url", False),
        # git's global options take an operand, which is not the subcommand
        ("git -C /repo diff", True),
        ("git -c color.ui=false log --oneline", True),
        ("git --no-pager log -3", True),
        ("git --git-dir=/x/.git status", True),
        ("git --git-dir /x/.git --work-tree /x status", True),
        ("git -C /a -C b log | head", True),
        ("cd /repo && git -C sub grep -n foo", True),
        ("git --version", True),
        ("git -C /repo", True),
        ("git -C /repo branch feature", False),
        ("git -C /repo branch -a", True),
        ("git -c user.name=x commit -m y", False),
        ("git -C /repo worktree add ../w", False),
        ("git -C /repo checkout main", False),
        # `env` runs the command after it; on its own it prints the environment
        ("env PYTHONPATH=. python -m pytest", False),
        ("env FOO=1 rg x .", True),
        ("env -i rg x .", True),
        ("env", True),
        ("env | grep PATH", True),
        ("printenv HOME", True),
        # an unquoted comment ends at the newline, which still separates stages
        ("cat a.py # inspect the file\npytest", False),
        ("cat a.py # pytest", True),
        ("cat a.py;# note\nls", True),
        ("# only a comment\nrg foo .", True),
        ("grep '#' a.py", True),
        ('grep "#" a.py', True),
        ("echo a#b", True),
        ("echo $# ${#x}", True),
        ("echo \\# ; pytest", False),
        # quoted operator characters are arguments, never operators
        ("grep -F '>' a.py", True),
        ("grep -c '|' a.py", True),
        ('rg ";" src', True),
        ("grep '&&' a.py", True),
        ('grep -F "(" a.py | wc -l', True),
        ("grep -F '<' a.py", True),
        ("git log --format='a\nb' -3", True),
        ("echo '>' > out.txt", False),
        ("echo '>' > '/dev/null'", True),
        ("cat a.py '|' pytest", True),
        ("grep -F '>' a.py; pytest", False),
    ],
)
def test_shell_is_readonly(command, readonly):
    assert shell_is_readonly(command) is readonly


def test_categories():
    assert categorize_hermes("read_file", None) == EXPLORATION
    assert categorize_hermes("terminal", json.dumps({"command": "cat x"})) == EXPLORATION
    assert categorize_hermes("terminal", json.dumps({"command": "pytest"})) == SHELL
    assert categorize_hermes("patch", None) == EDIT
    assert categorize_hermes("web_search", None) == WEB
    assert categorize_hermes("tool_search", None) == OTHER
    assert categorize_claude("Read", {}) == EXPLORATION
    assert categorize_claude("Bash", {"command": "rg foo"}) == EXPLORATION
    assert categorize_claude("Bash", {"command": "git -C /repo diff"}) == EXPLORATION
    assert categorize_claude("Bash", {"command": "git -C /repo commit"}) == SHELL
    assert categorize_claude("Bash", {"command": "env PYTHONPATH=. pytest"}) == SHELL
    assert categorize_claude("Bash", {"command": "grep -F '>' a.py"}) == EXPLORATION
    assert categorize_claude("Bash", {"command": "npm test"}) == SHELL
    assert categorize_claude("Edit", {}) == EDIT
    assert categorize_claude("mcp__x__y", {}) == OTHER


def test_parse_timestamps_default_to_utc():
    utc_midnight = 1_790_899_200  # 2026-10-02T00:00:00Z
    assert _parse("2026-10-02T00:00:00Z") == utc_midnight
    assert _parse("2026-10-02T00:00:00") == utc_midnight, "no offset means UTC, not local time"
    assert _parse("2026-10-02T02:00:00+02:00") == utc_midnight, "an explicit offset is kept"


def _tool_call(call_id: str, name: str, arguments: str) -> str:
    return json.dumps(
        [{"id": call_id, "type": "function", "function": {"name": name, "arguments": arguments}}]
    )


HERMES_SCHEMA = """
create table sessions (id text primary key, source text, model text, started_at real,
    ended_at real, system_prompt text, input_tokens int, output_tokens int,
    cache_read_tokens int, cache_write_tokens int);
create table messages (id integer primary key autoincrement, session_id text, role text,
    content text, tool_calls text, tool_name text, tool_call_id text, timestamp real,
    compacted int default 0, _compressed_summary int default 0, active int default 1,
    api_content text);
"""
INSERT_MSG = (
    "insert into messages (session_id, role, content, tool_calls, tool_name, tool_call_id, "
    "timestamp, compacted, _compressed_summary, active, api_content) "
    "values (?,?,?,?,?,?,?,?,?,?,?)"
)


def _hermes_db(path: Path) -> None:
    con = sqlite3.connect(path)
    con.executescript(HERMES_SCHEMA)
    con.execute(
        "insert into sessions values ('s1','cli','m',1000,1100,?,400,50,600,0)",
        ("S" * 40,),  # system prompt: 10 tokens
    )
    prompt = "P" * 40  # 10 tokens
    block = "\nCode matching this prompt:\n- a.py\n" + "B" * 8  # 40 chars -> 10 tokens
    rows = [
        ("user", prompt, None, None, None, 1001, 0, 0, 1, prompt + block),
        # call 1: present = system 10 + user 10 + block 10 = 30
        # the read's arguments "{}" are 1 token of exploration
        ("assistant", "", _tool_call("c1", "read_file", "{}"), None, None, 1002, 0, 0, 1, None),
        (
            "tool",
            "R" * 80,
            None,
            "read_file",
            "c1",
            1003,
            1,
            0,
            0,
            None,
        ),  # 20 tokens, compacted later
        # call 2: present = 30 + call-1 json + read 20; the pytest arguments are 5 tokens of shell
        (
            "assistant",
            "",
            _tool_call("c2", "terminal", json.dumps({"command": "pytest"})),
            None,
            None,
            1004,
            0,
            0,
            1,
            None,
        ),
        ("tool", "T" * 40, None, "terminal", "c2", 1005, 0, 0, 1, None),  # 10 tokens shell
        ("user", "", None, None, None, 1006, 0, 1, 1, None),  # compaction summary (empty)
        # call 3: read dropped; shell stays
        ("assistant", "done", None, None, None, 1007, 0, 0, 1, None),
    ]
    con.executemany(INSERT_MSG, [("s1",) + r for r in rows])
    # s2: not ended, last message at 1990 -> deferred when the window ends before that
    con.execute("insert into sessions values ('s2','cli','m',1400,NULL,'',100,10,0,0)")
    con.executemany(
        INSERT_MSG,
        [
            ("s2", "user", "hello", None, None, None, 1401, 0, 0, 1, None),
            ("s2", "assistant", "hi", None, None, None, 1990, 0, 0, 1, None),
        ],
    )
    # s3: billed 100 over 2 calls (budget 50 a call) but holds an active 200-token read
    con.execute("insert into sessions values ('s3','cli','m',1600,1700,'',100,10,0,0)")
    con.executemany(
        INSERT_MSG,
        [
            ("s3", "user", "U" * 40, None, None, None, 1601, 0, 0, 1, None),
            (
                "s3",
                "assistant",
                "",
                _tool_call("c9", "read_file", "{}"),
                None,
                None,
                1602,
                0,
                0,
                1,
                None,
            ),
            ("s3", "tool", "R" * 800, None, "read_file", "c9", 1603, 0, 0, 1, None),
            ("s3", "assistant", "done", None, None, None, 1604, 0, 0, 1, None),
        ],
    )
    con.commit()
    con.close()


def test_hermes_collector_presence_model(tmp_path):
    db = tmp_path / "state.db"
    _hermes_db(db)
    rows = hermes_db.collect(db, 0, 2000, TOK)
    assert [r.session_id for r in rows] == ["s1", "s2", "s3"]
    r = rows[0]
    assert r.source_group == "interactive"
    assert r.calls == 3
    assert r.prompt_tokens_billed == 1000
    assert r.first_tokens[EXPLORATION] == 21, "the read result (20) and its arguments (1)"
    assert r.first_tokens[BLOCK] == 10
    assert r.tool_calls == {EXPLORATION: 1, SHELL: 1}
    # the read (20) is present at call 2 only (compacted before call 3); its arguments,
    # on an uncompacted assistant row, stay present at calls 2 and 3
    assert r.billed_tokens[EXPLORATION] == 22
    # the block (10) is present at calls 1, 2 and 3
    assert r.billed_tokens[BLOCK] == 30
    # the shell result (10) and the pytest arguments (5) are present at call 3
    assert r.billed_tokens[SHELL] == 15
    assert r.compactions == 1 and r.trims == 0
    # the billing the transcript can't account for is counted as system
    assert r.context_tokens_est == 1000
    assert r.exploration_share == 22 / 1000
    # a rerun is idempotent: sessions that have written nothing since their rows are skipped
    seen = {"s1": r.last_activity, "s3": 1604}
    assert r.last_activity == 1007, "the session's latest message"
    assert [x.session_id for x in hermes_db.collect(db, 0, 2000, TOK, recorded=seen)] == ["s2"]


def test_hermes_collector_collects_again_a_session_that_has_written_since(tmp_path):
    db = tmp_path / "state.db"
    _hermes_db(db)
    first = hermes_db.collect(db, 0, 2000, TOK)
    s2 = {r.session_id: r for r in first}["s2"]
    # s2 had no ended_at when it was recorded: still running, however late the window ends
    assert s2.ended_at is None and s2.last_activity == 1990 and s2.calls == 1
    recorded = {r.session_id: r.last_activity for r in first}
    assert hermes_db.collect(db, 0, 2000, TOK, recorded=recorded) == []

    con = sqlite3.connect(db)
    con.execute(INSERT_MSG, ("s2", "assistant", "more", None, None, None, 1995, 0, 0, 1, None))
    con.commit()
    con.close()
    again = hermes_db.collect(db, 0, 2000, TOK, recorded=recorded)
    assert [r.session_id for r in again] == ["s2"], "only the session that grew"
    assert again[0].calls == 2 and again[0].last_activity == 1995

    # a row recorded without a last_activity cannot say whether it grew: collected once more
    unknown = {r.session_id: None for r in first}
    assert [r.session_id for r in hermes_db.collect(db, 0, 2000, TOK, recorded=unknown)] == [
        "s1",
        "s2",
        "s3",
    ]


def test_hermes_collector_defers_sessions_still_active(tmp_path):
    db = tmp_path / "state.db"
    _hermes_db(db)
    # window ends at 1500: s2 started inside it but was still writing at 1990
    assert [r.session_id for r in hermes_db.collect(db, 0, 1500, TOK)] == ["s1"]


def test_hermes_billing_cap_trims_active_results(tmp_path):
    db = tmp_path / "state.db"
    _hermes_db(db)
    r = [x for x in hermes_db.collect(db, 0, 2000, TOK) if x.session_id == "s3"][0]
    assert r.first_tokens[EXPLORATION] == 201
    # the 200-token read can't have been in a prompt that averaged 50 tokens: trimmed
    assert r.trims == 1
    assert r.billed_tokens.get(EXPLORATION, 0) <= 1
    assert r.context_tokens_est == r.prompt_tokens_billed == 100


def _claude_transcript(path: Path, billed: tuple[int, int, int]) -> None:
    def line(kind, content, ts, **extra):
        o = {"type": kind, "timestamp": ts, "sessionId": "cc1", "message": {"content": content}}
        o.update(extra)
        return json.dumps(o)

    def usage(n):
        return {
            "input_tokens": n,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
            "output_tokens": 7,
        }

    read_use = {"type": "tool_use", "id": "t1", "name": "Read", "input": {"file_path": "a.py"}}
    edit_use = {"type": "tool_use", "id": "t2", "name": "Edit", "input": {"file_path": "a.py"}}
    lines = [
        json.dumps({"type": "queue-operation"}),  # ignored
        line("user", "fix the bug", "2026-10-10T10:00:00Z"),  # 11 chars -> 2 tokens
        line(
            "user",
            [{"type": "text", "text": "Code matching this prompt:\n- a.py " + "B" * 6}],
            "2026-10-10T10:00:01Z",
        ),  # 40 chars -> 10 tokens, the block
        # call 1 (present: 12), written as two assistant lines with one requestId
        line(
            "assistant",
            [read_use],
            "2026-10-10T10:00:02Z",
            requestId="r1",
            message={"content": [read_use], "usage": usage(billed[0]), "model": "claude-x"},
        ),
        line(
            "assistant",
            [{"type": "text", "text": "reading"}],
            "2026-10-10T10:00:02Z",
            requestId="r1",
            message={"content": [{"type": "text", "text": "reading"}], "usage": usage(billed[0])},
        ),
        line(
            "user",
            [{"type": "tool_result", "tool_use_id": "t1", "content": "R" * 80}],
            "2026-10-10T10:00:03Z",
        ),  # 20 tokens exploration
        # call 2
        line(
            "assistant",
            [edit_use],
            "2026-10-10T10:00:04Z",
            requestId="r2",
            message={"content": [edit_use], "usage": usage(billed[1])},
        ),
        line(
            "user",
            [
                {
                    "type": "tool_result",
                    "tool_use_id": "t2",
                    "content": [{"type": "text", "text": "E" * 40}],
                }
            ],
            "2026-10-10T10:00:05Z",
        ),  # 10 tokens edit
        line("user", "summary of everything", "2026-10-10T10:00:06Z", isCompactSummary=True),
        # call 3
        line(
            "assistant",
            [{"type": "text", "text": "done"}],
            "2026-10-10T10:00:07Z",
            requestId="r3",
            message={"content": [{"type": "text", "text": "done"}], "usage": usage(billed[2])},
        ),
    ]
    path.write_text("\n".join(lines) + "\n")


def test_claude_code_collector(tmp_path):
    proj = tmp_path / "projects" / "-Users-x-repo"
    proj.mkdir(parents=True)
    # call 1 bills 400 for 12 tokens of content: overhead 388. Call 2's content is 12 + the
    # Read arguments (5, exploration) + "reading" (1) + the read result (20) = 38, billed
    # 426 = 388 + 38: no trim.
    _claude_transcript(proj / "cc1.jsonl", billed=(400, 426, 400))
    since = 1_700_000_000  # well before 2026
    rows = claude_code.collect(tmp_path / "projects", since, 2_000_000_000, TOK)
    assert len(rows) == 1
    r = rows[0]
    assert r.session_id == "cc1" and r.source_group == "interactive" and r.model == "claude-x"
    assert r.calls == 3, "two lines with one requestId are one API call"
    assert r.prompt_tokens_billed == 1226 and r.output_tokens_billed == 21
    assert r.first_tokens[EXPLORATION] == 25, "the Read's arguments (5) and its result (20)"
    assert r.first_tokens[EDIT] == 15, "the Edit's arguments (5) and its result (10)"
    assert r.first_tokens[BLOCK] == 10
    assert r.tool_calls == {EXPLORATION: 1, EDIT: 1}
    # the Read (arguments and result) is present at call 2 only (compaction before call 3);
    # the block at calls 1 and 2
    assert r.billed_tokens[EXPLORATION] == 25
    assert r.billed_tokens[BLOCK] == 20
    assert r.billed_tokens.get(EDIT, 0) == 0, "the edit was compacted before call 3"
    assert r.compactions == 1 and r.trims == 0
    assert r.billed_tokens["system"] == 3 * 388
    assert 0.95 < r.context_tokens_est / r.prompt_tokens_billed <= 1.0
    # a file outside the window is skipped
    assert claude_code.collect(tmp_path / "projects", 2_000_000_000, 2_100_000_000, TOK) == []
    # a session still writing after the window's end is deferred (last line is at 10:00:07Z)
    ends_at_10_00_05 = 1_791_626_405  # 2026-10-10T10:00:05Z
    assert claude_code.collect(tmp_path / "projects", since, ends_at_10_00_05, TOK) == []


def test_claude_code_collector_collects_again_a_session_that_has_written_since(tmp_path):
    proj = tmp_path / "projects" / "-Users-x-repo"
    proj.mkdir(parents=True)
    _claude_transcript(proj / "cc1.jsonl", billed=(400, 426, 400))
    since, until = 1_700_000_000, 2_000_000_000
    (r,) = claude_code.collect(tmp_path / "projects", since, until, TOK)
    assert r.last_activity == _parse("2026-10-10T10:00:07Z")
    assert (
        claude_code.collect(
            tmp_path / "projects", since, until, TOK, recorded={"cc1": r.last_activity}
        )
        == []
    )
    older = {"cc1": r.last_activity - 1}
    assert [
        x.session_id
        for x in claude_code.collect(tmp_path / "projects", since, until, TOK, recorded=older)
    ] == ["cc1"]
    unknown = {"cc1": None}
    assert [
        x.session_id
        for x in claude_code.collect(tmp_path / "projects", since, until, TOK, recorded=unknown)
    ] == ["cc1"]


def test_cli_replaces_the_row_of_a_session_that_has_written_since(tmp_path, capsys):
    proj = tmp_path / "projects" / "-Users-x-repo"
    proj.mkdir(parents=True)
    transcript = proj / "cc1.jsonl"
    _claude_transcript(transcript, billed=(400, 426, 400))
    out = tmp_path / "rows.jsonl"
    # rows of another agent in the same file (the README's commands share one) are never touched
    other = json.dumps({"agent": "hermes", "session_id": "cc1", "source_group": "interactive"})
    out.write_text(other + "\n")
    argv = ["claude-code", "--root", str(tmp_path / "projects"), "--since", "2026-01-01T00:00:00Z"]
    argv += ["--out", str(out), "--estimate"]

    assert main(argv) == 0
    assert "1 sessions added, 0 updated" in capsys.readouterr().out
    lines = out.read_text().splitlines()
    assert lines[0] == other and len(lines) == 2
    first = json.loads(lines[1])
    assert first["calls"] == 3 and first["last_activity"] == _parse("2026-10-10T10:00:07Z")

    # nothing written since: the file is not touched
    before = out.read_text()
    assert main(argv) == 0
    assert "0 sessions added, 0 updated" in capsys.readouterr().out
    assert out.read_text() == before

    # the session resumes: its row is replaced, not duplicated, and nothing is left behind
    resumed = {
        "type": "assistant",
        "timestamp": "2026-10-10T10:30:00Z",
        "sessionId": "cc1",
        "requestId": "r4",
        "message": {
            "content": [{"type": "text", "text": "more"}],
            "usage": {"input_tokens": 400, "output_tokens": 3},
        },
    }
    with transcript.open("a") as fh:
        fh.write(json.dumps(resumed) + "\n")
    assert main(argv) == 0
    assert "0 sessions added, 1 updated" in capsys.readouterr().out
    lines = out.read_text().splitlines()
    assert lines[0] == other and len(lines) == 2
    second = json.loads(lines[1])
    assert second["calls"] == 4 and second["last_activity"] == _parse("2026-10-10T10:30:00Z")
    assert not list(tmp_path.glob("*.tmp"))


def test_cli_keeps_the_first_of_two_transcripts_with_one_session_id(tmp_path, capsys):
    proj = tmp_path / "projects" / "-Users-x-repo"
    proj.mkdir(parents=True)
    _claude_transcript(proj / "a.jsonl", billed=(400, 426, 400))
    _claude_transcript(proj / "b.jsonl", billed=(500, 526, 500))  # same sessionId "cc1"
    out = tmp_path / "rows.jsonl"
    argv = ["claude-code", "--root", str(tmp_path / "projects"), "--since", "2026-01-01T00:00:00Z"]
    assert main(argv + ["--out", str(out), "--estimate"]) == 0
    assert "1 sessions added, 0 updated (1 interactive)" in capsys.readouterr().out
    (row,) = [json.loads(line) for line in out.read_text().splitlines()]
    assert (
        row["prompt_tokens_billed"] == 1226
    ), "a.jsonl, the first in path order, not b.jsonl's 1526"


def test_claude_code_billing_cap_trims_oldest_first(tmp_path):
    proj = tmp_path / "projects" / "-Users-x-repo"
    proj.mkdir(parents=True)
    # Billing stays at 400 while the transcript grows: call 2 can hold 12 tokens of content,
    # so everything older is trimmed, the 20-token read included.
    _claude_transcript(proj / "cc1.jsonl", billed=(400, 400, 400))
    r = claude_code.collect(tmp_path / "projects", 1_700_000_000, 2_000_000_000, TOK)[0]
    assert r.trims >= 1
    assert r.first_tokens[EXPLORATION] == 25
    assert r.billed_tokens.get(EXPLORATION, 0) == 0
    assert r.context_tokens_est <= r.prompt_tokens_billed


def test_claude_code_later_compaction_replaces_earlier_summary(tmp_path):
    proj = tmp_path / "projects" / "-Users-x-repo"
    proj.mkdir(parents=True)

    def line(kind, content, ts, **extra):
        o = {"type": kind, "timestamp": ts, "sessionId": "cc2", "message": {"content": content}}
        o.update(extra)
        return json.dumps(o)

    def call(req, n, ts):
        return line(
            "assistant",
            [{"type": "text", "text": "ok"}],
            ts,
            requestId=req,
            message={"content": [{"type": "text", "text": "ok"}], "usage": {"input_tokens": n}},
        )

    # "fix" is 1 token, each summary 10; overhead from call 1 is 399; calls 2 and 3 bill
    # 399 + 10, room for exactly one summary each
    lines = [
        line("user", "fix", "2026-10-10T10:00:00Z"),
        call("r1", 400, "2026-10-10T10:00:01Z"),
        line("user", "A" * 40, "2026-10-10T10:00:02Z", isCompactSummary=True),
        call("r2", 409, "2026-10-10T10:00:03Z"),
        line("user", "B" * 40, "2026-10-10T10:00:04Z", isCompactSummary=True),
        call("r3", 409, "2026-10-10T10:00:05Z"),
    ]
    (proj / "cc2.jsonl").write_text("\n".join(lines) + "\n")
    r = claude_code.collect(tmp_path / "projects", 1_700_000_000, 2_000_000_000, TOK)[0]
    assert r.compactions == 2
    assert r.billed_tokens["summary"] == 20, "summary A at call 2, summary B at call 3, never both"
    assert r.trims == 0
    assert r.context_tokens_est == r.prompt_tokens_billed == 1218


def test_report_aggregates_and_reads(tmp_path):
    db = tmp_path / "state.db"
    _hermes_db(db)
    rows = [r for r in hermes_db.collect(db, 0, 2000, TOK) if r.session_id == "s1"]
    out = tmp_path / "rows.jsonl"
    out.write_text(
        "".join(json.dumps(r.to_json()) + "\n" for r in rows) * 2
    )  # duplicated on purpose
    agg = report.aggregate(report.read_rows([out]))
    assert agg["n_sessions"] == 1, "duplicates are dropped by (agent, session_id)"
    g = agg["groups"]["hermes/interactive"]
    assert g["sessions"] == 1 and g["calls"] == 3
    assert g["exploration_share_billed"] == pytest.approx(22 / 1000)
    assert g["block_share_billed"] == pytest.approx(30 / 1000)
    assert g["calibration_est_over_billed"] == pytest.approx(1.0)
    assert agg["reading"]["hermes/interactive"].startswith("under 10%")
    md = report.to_markdown(agg, "t")
    assert "hermes/interactive" in md and "Pre-registered reading" in md
