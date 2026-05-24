"""
compressors.py — Token-reducing transforms for Claude Code tool outputs
========================================================================

Provides Pith-parity compression functions that run inside Claude Code
PostToolUse hooks:

1. compress_read(file_path, raw_content) → skeleton (uses graph if indexed)
2. compress_bash(stdout, stderr, exit_code) → errors + summary
3. cap_search_results(output, n) → truncate long grep/find output
4. offload_if_large(content) → write to tmp, return pointer

These functions are pure and framework-agnostic. They are wrapped by
`neuralmind/hooks.py` to integrate with Claude Code's PostToolUse protocol.

Design principles:
- Never lose critical information silently — always log what was trimmed
- Always provide an escape hatch ("for full output, do X")
- Fail-open: if compression fails, return the original content
"""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

# Size thresholds (tunable via env vars for tests and power users)
BASH_TAIL_LINES = int(os.environ.get("NEURALMIND_BASH_TAIL", "3"))
BASH_MAX_CHARS = int(os.environ.get("NEURALMIND_BASH_MAX_CHARS", "3000"))
# Failing commands under this size pass through verbatim — the ~200 byte
# compression marker would dwarf the actual output and add only noise.
BASH_SMALL_PASSTHROUGH = int(os.environ.get("NEURALMIND_BASH_SMALL", "500"))
SEARCH_MAX_MATCHES = int(os.environ.get("NEURALMIND_SEARCH_MAX", "25"))
OFFLOAD_THRESHOLD = int(os.environ.get("NEURALMIND_OFFLOAD_THRESHOLD", "15000"))

# Pattern to detect error/warning lines — conservative, broad enough for
# pytest / cargo / ffmpeg / webpack / tsc / npm
ERROR_PATTERN = re.compile(
    r"^(.*?)"
    r"(error|ERROR|Error|fail(ed|ure)?|FAIL|traceback|Traceback|exception|"
    r"panic|fatal|FATAL|E\d{3,4}:|Error:\s|\d+ errors?|\d+ passed|\d+ failed|"
    r"warning|WARNING|Warning:)",
    re.IGNORECASE,
)

# Lines that always make the cut (test counts, durations, summaries)
SUMMARY_PATTERN = re.compile(
    r"(^===+|^---+| passed| failed| error| warning|^OK\b|^PASS\b|^FAIL\b|"
    r"^Compiled |^Finished |^Done in |^real\s+\d|^user\s+\d|^Summary|test result:)",
    re.IGNORECASE,
)


def compress_bash(stdout: str, stderr: str, exit_code: int = 0) -> str:
    """Compress verbose bash output to errors + tail summary.

    Strategy:
    1. Small + successful → pass through unchanged (no marker, no noise).
    2. Small + failing → pass through verbatim with exit code framing.
       Adding a 200-byte compression marker to a 50-byte failure is pure
       noise and obscures the real output.
    3. Otherwise: extract every ERROR/WARNING/summary line, append the
       last N lines verbatim (usually the "FAILED" summary), and emit a
       footer that *categorizes* what was dropped so the reader can
       judge whether ``neuralmind last`` is worth running.

    Never drops stderr; always includes full exit context.
    """
    total_chars = len(stdout) + len(stderr)
    if total_chars <= BASH_MAX_CHARS and exit_code == 0:
        return _format_bash(stdout, stderr, exit_code)
    if total_chars <= BASH_SMALL_PASSTHROUGH:
        # Tiny failures: marker overhead would dwarf the content.
        return _format_bash(stdout, stderr, exit_code)

    def _important_lines(text: str) -> list[str]:
        lines = text.splitlines()
        keep: list[str] = []
        for line in lines:
            if ERROR_PATTERN.search(line) or SUMMARY_PATTERN.search(line):
                keep.append(line)
        return keep

    stdout_lines = stdout.splitlines() if stdout else []
    stderr_lines = stderr.splitlines() if stderr else []

    stdout_important = _important_lines(stdout)
    stderr_important = _important_lines(stderr)
    stdout_tail = stdout_lines[-BASH_TAIL_LINES:] if stdout_lines else []
    stderr_tail = stderr_lines[-BASH_TAIL_LINES:] if stderr_lines else []

    # Emit (important + tail) deduped, preserving order. Track the
    # multiset of lines actually emitted so the dropped-summary can
    # subtract correctly — a line that appeared 30× in the original but
    # was emitted once is "29 dropped", not "0 dropped".
    parts: list[str] = [f"[neuralmind: bash compressed, exit={exit_code}]"]
    emitted_stdout: list[str] = []
    if stdout_important or stdout_tail:
        parts.append("# stdout (key lines + tail):")
        seen: set[str] = set()
        for line in stdout_important + stdout_tail:
            if line not in seen:
                parts.append(line)
                emitted_stdout.append(line)
                seen.add(line)
    emitted_stderr: list[str] = []
    if stderr_important or stderr_tail:
        parts.append("# stderr (key lines + tail):")
        seen = set()
        for line in stderr_important + stderr_tail:
            if line not in seen:
                parts.append(line)
                emitted_stderr.append(line)
                seen.add(line)

    dropped_summary = _summarize_dropped(
        stdout_lines, emitted_stdout, stderr_lines, emitted_stderr
    )
    size_hint = f"{len(stdout)} B stdout"
    if stderr:
        size_hint += f" + {len(stderr)} B stderr"
    if dropped_summary:
        parts.append(
            f"[neuralmind: dropped {dropped_summary} · {size_hint} total · "
            "`neuralmind last` for cached raw · NEURALMIND_BYPASS=1 to disable]"
        )
    else:
        parts.append(
            f"[neuralmind: nothing dropped · {size_hint} total · "
            "`neuralmind last` for cached raw · NEURALMIND_BYPASS=1 to disable]"
        )
    return "\n".join(parts)


# Common log-level prefixes used by node/winston, python logging, rust env_logger,
# go-kit, structured loggers, etc. Kept conservative — we only want confident
# matches so the categorized summary stays accurate.
_LOG_LEVEL_PATTERNS = [
    ("debug", re.compile(r"^\s*(\[?\s*(DEBUG|TRACE|debug|trace)\b|\w*\s+debug:)")),
    ("info", re.compile(r"^\s*(\[?\s*(INFO|info)\b|\w*\s+info:)")),
    ("warn", re.compile(r"^\s*\[?\s*(WARN(ING)?|warn(ing)?)\b")),
]


def _categorize_line(line: str) -> str:
    """Return a short label for a dropped line — one of debug/info/warn/blank/other."""
    if not line.strip():
        return "blank"
    for label, pattern in _LOG_LEVEL_PATTERNS:
        if pattern.search(line):
            return label
    return "other"


def _summarize_dropped(
    stdout_lines: list[str],
    emitted_stdout: list[str],
    stderr_lines: list[str],
    emitted_stderr: list[str],
) -> str:
    """Categorize what got dropped from a compressed stream.

    Returns a compact human-readable string like:
        "12 lines (8 info, 4 other); repeated: 5× 'Gamma API error 503'"

    Empty string means nothing was dropped (every occurrence in the
    original streams was emitted exactly once or more).
    """
    from collections import Counter

    original_counts: Counter[str] = Counter(stdout_lines) + Counter(stderr_lines)
    emitted_counts: Counter[str] = Counter(emitted_stdout) + Counter(emitted_stderr)

    # Diff with multiplicity: lines kept once but originally repeated N times
    # still contribute (N-1) to the dropped tally — that's the user-visible
    # information loss from dedup, not just literal omission.
    dropped_counts = original_counts - emitted_counts
    if not dropped_counts:
        return ""

    total_dropped = sum(dropped_counts.values())
    cats: Counter[str] = Counter()
    for line, n in dropped_counts.items():
        cats[_categorize_line(line)] += n
    cat_str = ", ".join(
        f"{n} {label}" for label, n in cats.most_common() if n
    )

    # Repeated-line detection — surface only patterns that show up 5+
    # times since that's where dedup meaningfully shrinks reader load.
    nonblank = {ln.strip(): n for ln, n in dropped_counts.items() if ln.strip()}
    repeated = sorted(nonblank.items(), key=lambda kv: -kv[1])[:2]
    repeated = [(t, n) for t, n in repeated if n >= 5]

    summary = f"{total_dropped} lines ({cat_str})"
    if repeated:
        rep_str = "; ".join(f"{n}× {text[:50]!r}" for text, n in repeated)
        summary += f"; repeated: {rep_str}"
    return summary


def _format_bash(stdout: str, stderr: str, exit_code: int) -> str:
    """Standard bash output formatting when no compression is needed."""
    parts: list[str] = []
    if stdout:
        parts.append(stdout.rstrip())
    if stderr:
        parts.append(f"[stderr]\n{stderr.rstrip()}")
    if exit_code != 0:
        parts.append(f"[exit code: {exit_code}]")
    return "\n".join(parts) if parts else "(empty output)"


def compress_read(file_path: str, raw_content: str, mind=None) -> str:
    """Replace raw file content with a graph-backed skeleton when possible.

    Args:
        file_path: Path of the file being read
        raw_content: Original file content from Claude Code's Read tool
        mind: Optional NeuralMind instance; if None, we try to auto-load

    Returns the skeleton if the file is indexed, else the raw content.
    """
    if os.environ.get("NEURALMIND_BYPASS") == "1":
        return raw_content
    # Files under a certain size aren't worth compressing
    if len(raw_content) < 1500:
        return raw_content

    try:
        from .core import NeuralMind  # local to avoid circular import at module-load

        if mind is None:
            # Walk up from file_path looking for graphify-out
            search_from = Path(file_path).resolve().parent
            for candidate in [search_from, *search_from.parents]:
                if (candidate / "graphify-out" / "graph.json").exists():
                    mind = NeuralMind(str(candidate))
                    break
            else:
                return raw_content  # No index anywhere up the tree

        skeleton = mind.skeleton(file_path)
        if skeleton and skeleton != "":
            return (
                skeleton
                + f"\n\n[neuralmind: compressed from {len(raw_content)} chars. Full source: set NEURALMIND_BYPASS=1]"
            )
        return raw_content
    except Exception:
        # Fail open — never break a Read just because compression failed
        return raw_content


def cap_search_results(output: str, max_matches: int | None = None) -> str:
    """Truncate grep/find/ripgrep output at N matches."""
    if os.environ.get("NEURALMIND_BYPASS") == "1":
        return output
    limit = max_matches if max_matches is not None else SEARCH_MAX_MATCHES

    lines = output.splitlines()
    # Each non-empty line is typically a match (for grep -n, rg, find)
    match_lines = [ln for ln in lines if ln.strip()]
    if len(match_lines) <= limit:
        return output

    kept = match_lines[:limit]
    suffix = (
        f"\n[neuralmind: capped at {limit} matches. "
        f"{len(match_lines) - limit} more hidden. "
        "Refine your query or set NEURALMIND_BYPASS=1 to see all.]"
    )
    return "\n".join(kept) + suffix


def offload_if_large(
    content: str, threshold: int | None = None, prefix: str = "nm_offload_"
) -> tuple[str, Path | None]:
    """Offload oversize content to a temp file, return a pointer message.

    Useful for large JSON / HTML / binary tool outputs that flood context.

    Returns:
        (message, path): If content > threshold, message is a summary referencing
        path. Else, message is the original content and path is None.
    """
    if os.environ.get("NEURALMIND_BYPASS") == "1":
        return content, None

    limit = threshold if threshold is not None else OFFLOAD_THRESHOLD
    if len(content) <= limit:
        return content, None

    # Write full content to temp file
    fd, tmp_path = tempfile.mkstemp(prefix=prefix, suffix=".txt", text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception:
        return content, None  # fail open

    path = Path(tmp_path)
    # First 500 chars + last 500 chars as a preview
    head = content[:500]
    tail = content[-500:]
    summary = (
        f"[neuralmind: content offloaded ({len(content)} chars → {path})]\n"
        f"--- head (500 chars) ---\n{head}\n"
        f"--- tail (500 chars) ---\n{tail}\n"
        f"[Full content at: {path}]"
    )
    return summary, path
