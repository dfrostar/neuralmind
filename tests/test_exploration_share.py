"""Exploration-share collectors (stdlib only; tiktoken is bypassed with chars/4).

The presence model: a message is paid for by every API call after it until a
compaction drops it, or until the context size the provider billed for a call
says it must have been trimmed (oldest droppable messages first). With chars/4
counting, a 40-character tool result is 10 tokens, so the numbers below are
exact.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from evals.exploration_share import claude_code, hermes_db, report
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
        ("pytest tests/ 2>&1 | tail -5", False),
        ("pip install tiktoken", False),
        ("echo hi > /dev/null", True),
        ("FOO=1 rg pattern .", True),
        ("", False),
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
    assert categorize_claude("Bash", {"command": "npm test"}) == SHELL
    assert categorize_claude("Edit", {}) == EDIT
    assert categorize_claude("mcp__x__y", {}) == OTHER


def _tool_call(call_id: str, name: str, arguments: str) -> str:
    return json.dumps(
        [{"id": call_id, "type": "function", "function": {"name": name, "arguments": arguments}}]
    )


def _hermes_db(path: Path) -> None:
    con = sqlite3.connect(path)
    con.executescript("""
        create table sessions (id text primary key, source text, model text, started_at real,
            ended_at real, system_prompt text, input_tokens int, output_tokens int,
            cache_read_tokens int, cache_write_tokens int);
        create table messages (id integer primary key autoincrement, session_id text, role text,
            content text, tool_calls text, tool_name text, tool_call_id text, timestamp real,
            compacted int default 0, _compressed_summary int default 0, active int default 1,
            api_content text);
        """)
    con.execute(
        "insert into sessions values ('s1','cli','m',1000,1100,?,400,50,600,0)",
        ("S" * 40,),  # system prompt: 10 tokens
    )
    prompt = "P" * 40  # 10 tokens
    block = "\nCode matching this prompt:\n- a.py\n" + "B" * 8  # 40 chars -> 10 tokens
    rows = [
        ("user", prompt, None, None, None, 1001, 0, 0, 1, prompt + block),
        # call 1: present = system 10 + user 10 + block 10 = 30
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
        # call 2: present = 30 + assistant(tool_calls json) + read 20
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
    con.executemany(
        "insert into messages (session_id, role, content, tool_calls, tool_name, tool_call_id, "
        "timestamp, compacted, _compressed_summary, active, api_content) "
        "values ('s1',?,?,?,?,?,?,?,?,?,?)",
        rows,
    )
    con.commit()
    con.close()


def test_hermes_collector_presence_model(tmp_path):
    db = tmp_path / "state.db"
    _hermes_db(db)
    rows = hermes_db.collect(db, 0, 2000, TOK)
    assert len(rows) == 1
    r = rows[0]
    assert r.source_group == "interactive"
    assert r.calls == 3
    assert r.prompt_tokens_billed == 1000
    assert r.first_tokens[EXPLORATION] == 20
    assert r.first_tokens[BLOCK] == 10
    assert r.tool_calls == {EXPLORATION: 1, SHELL: 1}
    # the read (20) is present at call 2 only: compacted before call 3
    assert r.billed_tokens[EXPLORATION] == 20
    # the block (10) is present at calls 1, 2 and 3
    assert r.billed_tokens[BLOCK] == 30
    # the shell result (10) is present at call 3 only
    assert r.billed_tokens[SHELL] == 10
    assert r.compactions == 1 and r.trims == 0
    # the billing the transcript can't account for is spread over the calls as system
    assert r.context_tokens_est == 1000
    assert r.exploration_share == 20 / 1000
    # skip_ids makes a rerun idempotent
    assert hermes_db.collect(db, 0, 2000, TOK, skip_ids={"s1"}) == []


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
    # tool_use json (5) + "reading" (1) + the read (20) = 38, billed 426 = 388 + 38: no trim.
    _claude_transcript(proj / "cc1.jsonl", billed=(400, 426, 400))
    since = 1_700_000_000  # well before 2026
    rows = claude_code.collect(tmp_path / "projects", since, 2_000_000_000, TOK)
    assert len(rows) == 1
    r = rows[0]
    assert r.session_id == "cc1" and r.source_group == "interactive" and r.model == "claude-x"
    assert r.calls == 3, "two lines with one requestId are one API call"
    assert r.prompt_tokens_billed == 1226 and r.output_tokens_billed == 21
    assert r.first_tokens[EXPLORATION] == 20 and r.first_tokens[EDIT] == 10
    assert r.first_tokens[BLOCK] == 10
    assert r.tool_calls == {EXPLORATION: 1, EDIT: 1}
    # read result present at call 2 only (compaction before call 3); block at calls 1 and 2
    assert r.billed_tokens[EXPLORATION] == 20
    assert r.billed_tokens[BLOCK] == 20
    assert r.billed_tokens.get(EDIT, 0) == 0, "the edit result was compacted before call 3"
    assert r.compactions == 1 and r.trims == 0
    assert r.billed_tokens["system"] == 3 * 388
    assert 0.95 < r.context_tokens_est / r.prompt_tokens_billed <= 1.0
    # a file outside the window is skipped
    assert claude_code.collect(tmp_path / "projects", 2_000_000_000, 2_100_000_000, TOK) == []


def test_claude_code_billing_cap_trims_oldest_first(tmp_path):
    proj = tmp_path / "projects" / "-Users-x-repo"
    proj.mkdir(parents=True)
    # Billing stays at 400 while the transcript grows: call 2 can hold 12 tokens of content,
    # so everything older is trimmed, the 20-token read included.
    _claude_transcript(proj / "cc1.jsonl", billed=(400, 400, 400))
    r = claude_code.collect(tmp_path / "projects", 1_700_000_000, 2_000_000_000, TOK)[0]
    assert r.trims >= 1
    assert r.first_tokens[EXPLORATION] == 20
    assert r.billed_tokens.get(EXPLORATION, 0) == 0
    assert r.context_tokens_est <= r.prompt_tokens_billed


def test_report_aggregates_and_reads(tmp_path):
    db = tmp_path / "state.db"
    _hermes_db(db)
    rows = hermes_db.collect(db, 0, 2000, TOK)
    out = tmp_path / "rows.jsonl"
    out.write_text(
        "".join(json.dumps(r.to_json()) + "\n" for r in rows) * 2
    )  # duplicated on purpose
    agg = report.aggregate(report.read_rows([out]))
    assert agg["n_sessions"] == 1, "duplicates are dropped by (agent, session_id)"
    g = agg["groups"]["hermes/interactive"]
    assert g["sessions"] == 1 and g["calls"] == 3
    assert g["exploration_share_billed"] == pytest.approx(20 / 1000)
    assert g["block_share_billed"] == pytest.approx(30 / 1000)
    assert g["calibration_est_over_billed"] == pytest.approx(1.0)
    assert agg["reading"]["hermes/interactive"].startswith("under 10%")
    md = report.to_markdown(agg, "t")
    assert "hermes/interactive" in md and "Pre-registered reading" in md
