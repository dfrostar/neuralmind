"""Collector over Claude Code transcripts (``~/.claude/projects/*/*.jsonl``)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .classify import categorize_claude
from .rows import BLOCK, BLOCK_MARKER, Context, SessionRow, count_tool
from .tokens import Tokenizer


def collect(
    root: str | Path,
    since: float,
    until: float,
    tokenizer: Tokenizer | None = None,
    skip_ids: set[str] | None = None,
) -> list[SessionRow]:
    tok = tokenizer or Tokenizer()
    rows: list[SessionRow] = []
    for path in sorted(Path(root).expanduser().glob("*/*.jsonl")):
        if path.stat().st_mtime < since:
            continue  # nothing written in the window
        row = _collect_file(path, since, until, tok)
        if row is not None and not (skip_ids and row.session_id in skip_ids):
            rows.append(row)
    return rows


def _ts(value) -> float | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _text_of(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            b.get("text", "") if isinstance(b, dict) and b.get("type") == "text" else json.dumps(b)
            for b in content
        )
    return "" if content is None else json.dumps(content)


def _collect_file(path: Path, since: float, until: float, tok: Tokenizer) -> SessionRow | None:
    row: SessionRow | None = None
    ctx: Context | None = None
    seen_requests: set[str] = set()
    tool_inputs: dict[str, tuple[str, dict]] = {}
    sidechain = False
    first_ts: float | None = None
    last_ts: float | None = None
    overhead: int | None = None  # prompt the transcript doesn't hold, from the first billed call
    with path.open() as fh:
        for line in fh:
            try:
                o = json.loads(line)
            except json.JSONDecodeError:
                continue
            kind = o.get("type")
            if kind == "attachment" and ctx is not None:
                # system-reminders injected into the next user turn (CLAUDE.md, hook output, …)
                for part in o.get("rendered") or []:
                    _add_user_text(ctx, tok, str((part or {}).get("content", "")))
                continue
            if kind not in ("user", "assistant"):
                continue
            ts = _ts(o.get("timestamp"))
            if first_ts is None and ts is not None:
                first_ts = ts
                if not (since <= first_ts < until):
                    return None
            if ts is not None:
                last_ts = ts
            if row is None:
                sidechain = bool(o.get("isSidechain"))
                row = SessionRow(
                    agent="claude-code",
                    session_id=str(o.get("sessionId") or path.stem),
                    source="sidechain" if sidechain else "session",
                    source_group="subagent" if sidechain else "interactive",
                    started_at=first_ts,
                    ended_at=None,
                    model=None,
                    tokenizer=tok.name,
                )
                ctx = Context(row)
            assert row is not None and ctx is not None
            msg = o.get("message") or {}
            content = msg.get("content")
            if kind == "assistant":
                req = str(o.get("requestId") or msg.get("id") or o.get("uuid"))
                if req not in seen_requests:
                    seen_requests.add(req)
                    usage = msg.get("usage") or {}
                    billed = (
                        (usage.get("input_tokens") or 0)
                        + (usage.get("cache_read_input_tokens") or 0)
                        + (usage.get("cache_creation_input_tokens") or 0)
                    )
                    if billed:
                        # The provider's count is the context size at this call. The first
                        # call fixes the overhead (system prompt, tool schemas); later calls
                        # that bill less than the transcript holds were trimmed, oldest first.
                        if overhead is None:
                            overhead = max(0, billed - ctx.present_total)
                        ctx.cap(max(0, billed - overhead))
                        ctx.call(overhead)
                    else:
                        ctx.call()
                    row.prompt_tokens_billed += billed
                    row.output_tokens_billed += usage.get("output_tokens") or 0
                    row.model = row.model or msg.get("model")
                for b in content if isinstance(content, list) else []:
                    if not isinstance(b, dict):
                        continue
                    if b.get("type") == "tool_use":
                        tool_inputs[str(b.get("id"))] = (str(b.get("name")), b.get("input") or {})
                        ctx.add("assistant", tok.count(json.dumps(b.get("input") or {})))
                    elif b.get("type") == "text":
                        ctx.add("assistant", tok.count(b.get("text", "")))
                    elif b.get("type") == "thinking":
                        # interleaved thinking is sent back with the conversation
                        ctx.add("assistant", tok.count(b.get("thinking", "")))
                if isinstance(content, str):
                    ctx.add("assistant", tok.count(content))
                continue
            # user line
            if o.get("isCompactSummary"):
                # the summary replaces everything before it, earlier summaries included,
                # and is itself replaced by the next one
                ctx.compact()
                ctx.add("summary", tok.count(_text_of(content)))
                continue
            if isinstance(content, str):
                _add_user_text(ctx, tok, content)
                continue
            for b in content if isinstance(content, list) else []:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "tool_result":
                    name, tool_input = tool_inputs.get(str(b.get("tool_use_id")), ("", {}))
                    category = categorize_claude(name, tool_input)
                    count_tool(row, category)
                    ctx.add(category, tok.count(_text_of(b.get("content"))))
                elif b.get("type") == "text":
                    _add_user_text(ctx, tok, b.get("text", ""))
    if row is None:
        return None
    if last_ts is not None and last_ts > until:
        return None  # still active after the window's end: deferred, so it isn't recorded half-way
    row.ended_at = last_ts
    return row


def _add_user_text(ctx: Context, tok: Tokenizer, text: str) -> None:
    if BLOCK_MARKER in text:
        ctx.add(BLOCK, tok.count(text))
    else:
        ctx.add("user", tok.count(text))
