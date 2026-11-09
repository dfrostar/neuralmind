# SPDX-License-Identifier: MIT
"""Collector over Hermes's ``state.db`` (opened read-only)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .classify import categorize_hermes
from .rows import BLOCK, Context, SessionRow, count_tool
from .tokens import Tokenizer

SOURCE_GROUPS = {
    "cli": "interactive",
    "desktop": "interactive",
    "local": "interactive",
    "telegram": "interactive",
    "discord": "interactive",
    "signal": "interactive",
    "cron": "automated",
    "oneshot": "automated",
    "a2a": "automated",
    "api_server": "automated",
    "subagent": "subagent",
    "tool": "benchmark",
}

SESSIONS_SQL = """
select id, source, model, started_at, ended_at, system_prompt,
       input_tokens, output_tokens, cache_read_tokens, cache_write_tokens
from sessions
where started_at >= ? and started_at < ?
order by started_at
"""
CALLS_SQL = "select count(*) from messages where session_id = ? and role = 'assistant'"
LAST_TS_SQL = "select max(timestamp) from messages where session_id = ?"
MESSAGES_SQL = """
select role, content, tool_calls, tool_name, tool_call_id, timestamp,
       compacted, _compressed_summary, active, api_content
from messages where session_id = ?
order by timestamp, id
"""


def open_readonly(db_path: str | Path) -> sqlite3.Connection:
    # as_uri() percent-encodes the path (a `?`, `#` or `%` in it would otherwise end the
    # URI early) and writes a Windows drive path as sqlite expects it.
    uri = Path(db_path).expanduser().absolute().as_uri()
    return sqlite3.connect(f"{uri}?mode=ro", uri=True)


def collect(
    db_path: str | Path,
    since: float,
    until: float,
    tokenizer: Tokenizer | None = None,
    recorded: dict[str, float | None] | None = None,
) -> list[SessionRow]:
    """Sessions started in [since, until) and finished by ``until``.

    ``recorded`` maps a session id to the latest activity its recorded row holds: a
    session is skipped only while it has written nothing newer, so one recorded
    half-way (or resumed since) is collected again and its row replaced.
    """
    tok = tokenizer or Tokenizer()
    con = open_readonly(db_path)
    rows: list[SessionRow] = []
    for sess in con.execute(SESSIONS_SQL, (since, until)):
        sid, source, model, started, ended, system_prompt, in_tok, out_tok, cr_tok, cw_tok = sess
        last_ts = con.execute(LAST_TS_SQL, (sid,)).fetchone()[0]
        # One still active at the window's end is deferred to a later run rather than
        # recorded half-way: ended after `until`, or writing after it.
        if (ended is not None and ended > until) or (last_ts is not None and last_ts > until):
            continue
        activity = last_ts if last_ts is not None else (ended if ended is not None else started)
        if recorded is not None and sid in recorded:
            before = recorded[sid]
            if before is not None and activity is not None and activity <= before:
                continue  # nothing newer than the row already recorded
        row = SessionRow(
            agent="hermes",
            session_id=sid,
            source=source or "",
            source_group=SOURCE_GROUPS.get(source or "", "automated"),
            started_at=started,
            ended_at=ended,
            last_activity=activity,
            model=model,
            tokenizer=tok.name,
            prompt_tokens_billed=(in_tok or 0) + (cr_tok or 0) + (cw_tok or 0),
            output_tokens_billed=out_tok or 0,
        )
        ctx = Context(row)
        ctx.add("system", tok.count(system_prompt), compactable=False, trimmable=False)
        call_args: dict[str, tuple[str, str | None]] = {}
        # Hermes bills per session, not per call: the mean prompt size caps each call's
        # content (oldest messages dropped first), and whatever the billing exceeds
        # the transcript by (tool schemas, not stored) is counted as system.
        n_calls = con.execute(CALLS_SQL, (sid,)).fetchone()[0] or 0
        budget = (
            row.prompt_tokens_billed // n_calls if n_calls and row.prompt_tokens_billed else None
        )
        for msg in con.execute(MESSAGES_SQL, (sid,)):
            (
                role,
                content,
                tool_calls,
                tool_name,
                tool_call_id,
                _ts,
                compacted,
                is_summary,
                active,
                api_content,
            ) = msg
            # what the next compression removes, as Hermes recorded it on the row
            compactable = bool(compacted) or not active
            if is_summary:
                ctx.compact()
                ctx.add("summary", tok.count(content), compactable)
                continue
            if role == "assistant":
                if budget is not None:
                    ctx.cap(budget)
                ctx.call()
                calls = _parse_tool_calls(tool_calls)
                args_tokens = 0
                for name, args, call_id in calls:
                    call_args[call_id] = (name, args)
                    # the call's arguments (a path, a pattern, a command) count with its category
                    n = tok.count(args)
                    args_tokens += n
                    ctx.add(categorize_hermes(name, args), n, compactable)
                wrapper = max(0, tok.count(tool_calls) - args_tokens)
                ctx.add("assistant", tok.count(content) + wrapper, compactable)
            elif role == "tool":
                name, args = call_args.get(tool_call_id or "", (tool_name, None))
                category = categorize_hermes(name or tool_name, args)
                count_tool(row, category)
                ctx.add(category, tok.count(content), compactable)
            elif role == "user":
                ctx.add("user", tok.count(content), compactable)
                block = _block_of(content, api_content)
                if block:
                    ctx.add(BLOCK, tok.count(block), compactable)
            # session_meta and anything else: not part of the prompt
        if row.calls and row.prompt_tokens_billed > row.context_tokens_est:
            overhead = row.prompt_tokens_billed - row.context_tokens_est
            row.context_tokens_est += overhead
            row.billed_tokens["system"] = row.billed_tokens.get("system", 0) + overhead
        rows.append(row)
    con.close()
    return rows


def _parse_tool_calls(tool_calls: str | None) -> list[tuple[str, str | None, str]]:
    if not tool_calls:
        return []
    try:
        calls = json.loads(tool_calls)
    except Exception:
        return []
    out = []
    for c in calls if isinstance(calls, list) else []:
        if not isinstance(c, dict):
            continue
        fn = c.get("function") or {}
        name = fn.get("name") or c.get("name") or ""
        args = fn.get("arguments") if isinstance(fn, dict) else None
        call_id = c.get("id") or c.get("call_id") or ""
        out.append(
            (name, args if isinstance(args, str) else json.dumps(args) if args else None, call_id)
        )
    return out


def _block_of(content: str | None, api_content: str | None) -> str | None:
    """The plugin appends its block to the user's text: api_content = content + block."""
    if not api_content or api_content == content:
        return None
    if content and api_content.startswith(content):
        return api_content[len(content) :]
    return None
