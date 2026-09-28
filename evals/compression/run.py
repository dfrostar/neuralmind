"""Measure what NeuralMind's PostToolUse hooks do to the tokens Claude sees.

    python -m evals.compression.run --work-dir .bench-work --out bench/compression

Every sample is one tool call, measured three ways:

``baseline``
    The tool result as Claude Code delivers it, with no hook installed.
``as_shipped``
    The same call with ``neuralmind install-hooks`` in place. The real hook
    entry point (:func:`neuralmind.hooks.run_hook`) receives a payload shaped
    like Claude Code's, and its JSON response is applied the way Claude Code's
    documented hook protocol applies it. This is what NeuralMind users get.
``compressor_only``
    Hypothetical: the compressor's output delivered *instead of* the result,
    which is what a hook returning ``updatedToolOutput`` would deliver. It is
    reported next to what it keeps, because a smaller result that drops the
    failing assertion or the code about to be edited is not a saving.

Protocol facts the simulation encodes, from Claude Code's hooks reference
(https://code.claude.com/docs/en/hooks) and tools reference
(https://code.claude.com/docs/en/tools-reference), both read on 2026-09-28:

* PostToolUse fires only after a tool succeeded. A Bash command Claude Code
  treats as failed fires PostToolUseFailure, which can add context but cannot
  replace the result. NeuralMind registers PostToolUse only.
* PostToolUse ``additionalContext`` is "added to Claude's context alongside the
  tool result". A value over 10,000 characters becomes a file path plus a
  preview of its first 2,000 characters.
* ``updatedToolOutput`` replaces the result, and must match the tool's output
  shape or it is ignored.
* A valid Bash result is inline up to ~30,000 characters, then a file path plus
  a 2,000-character preview. A failed one is ``Exit code N`` plus the output,
  inline up to ~10,000 characters, then a head-and-tail excerpt. Exit 1 counts
  as valid only for grep, rg, egrep, fgrep, find, diff, test, ``[``, git diff
  and git grep.
* Read returns line-number-prefixed text. Grep's content mode returns
  ``path:line:text`` lines (250 by default); its default mode lists file paths.

``tool_response`` payloads follow the output types in the Agent SDK's
``sdk-tools.d.ts`` (:data:`SDK_SHAPES`). Tokens are counted with the public
benchmark's tokenizer (tiktoken ``o200k_base``). The system-reminder wrapper
Claude Code puts around ``additionalContext`` is not counted, so the
``as_shipped`` cost is, if anything, understated.
"""

from __future__ import annotations

import argparse
import ast
import contextlib
import hashlib
import io
import json
import os
import re
import shlex
import statistics
import sys
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

from evals.public.run import _build_nm, ensure_checkout, load_manifest
from evals.public.tokens import count_tokens, tokenizer_name

REPO_ROOT = Path(__file__).resolve().parents[2]
CORPUS_DIR = Path(__file__).with_name("corpus") / "bash"
DEFAULT_OUT = REPO_ROOT / "bench" / "compression"

SDK_SHAPES = "@anthropic-ai/claude-agent-sdk 0.3.283 sdk-tools.d.ts (Claude Code 2.1.283)"
DOCS_READ_ON = "2026-09-28"
DOCS = [
    "https://code.claude.com/docs/en/hooks",
    "https://code.claude.com/docs/en/tools-reference",
]

ADDITIONAL_CONTEXT_CAP = 10_000
OVERFLOW_PREVIEW = 2_000
BASH_VALID_INLINE = 30_000
BASH_FAILURE_INLINE = 10_000
GREP_HEAD_LIMIT = 250
# Read pages files past a token limit (CLAUDE_CODE_FILE_READ_MAX_OUTPUT_TOKENS;
# the docs don't state its default). Whole files above this size may reach
# Claude as a partial first page, so the Read summary also reports the
# compressor figure without them.
READ_PAGE_SENSITIVITY = 25_000
BENIGN_EXIT_1 = {"grep", "rg", "egrep", "fgrep", "find", "diff", "test", "["}

# Compressor thresholds are module constants read from the environment at
# import time; a run with any of these set would not measure the defaults.
_THRESHOLD_ENV = (
    "NEURALMIND_BYPASS",
    "NEURALMIND_BASH_TAIL",
    "NEURALMIND_BASH_MAX_CHARS",
    "NEURALMIND_BASH_SMALL",
    "NEURALMIND_SEARCH_MAX",
)

# Grep patterns every repo is searched for, on top of its public-benchmark
# oracle symbols: the broad searches an agent runs while orienting.
BROAD_PATTERNS = [
    r"^\s*import |^\s*from \S+ import ",
    r"\braise\b",
    r"def __init__",
    r"self\.\w+ =",
]


# --------------------------------------------------------------------------
# What Claude Code puts in front of the model
# --------------------------------------------------------------------------


def _overflow(text: str, cap: int, label: str) -> str:
    """Claude Code's treatment of an oversized string: a path plus a preview."""
    if len(text) <= cap:
        return text
    return (
        f"[{label}: {len(text)} characters saved to <session-dir>/{label}.txt; "
        f"first {OVERFLOW_PREVIEW} characters:]\n{text[:OVERFLOW_PREVIEW]}"
    )


def _is_valid_bash(command: str, exit_code: int) -> bool:
    if exit_code == 0:
        return True
    if exit_code != 1:
        return False
    try:
        argv = shlex.split(command)
    except ValueError:
        return False
    if not argv:
        return False
    if argv[0] == "git" and len(argv) > 1 and argv[1] in ("diff", "grep"):
        return True
    return Path(argv[0]).name in BENIGN_EXIT_1


def _join_streams(stdout: str, stderr: str) -> str:
    parts = [s.rstrip("\n") for s in (stdout, stderr) if s]
    return "\n".join(parts)


def bash_result(stdout: str, stderr: str, exit_code: int, command: str) -> tuple[str, bool]:
    """The Bash tool result Claude receives, and whether it counts as valid."""
    valid = _is_valid_bash(command, exit_code)
    body = _join_streams(stdout, stderr)
    if valid:
        return _overflow(body, BASH_VALID_INLINE, "bash-output"), True
    text = f"Exit code {exit_code}\n{body}"
    if len(text) > BASH_FAILURE_INLINE:
        half = BASH_FAILURE_INLINE // 2
        dropped = len(text) - 2 * half
        text = f"{text[:half]}\n... [{dropped} characters truncated] ...\n{text[-half:]}"
    return text, False


def read_result(content: str) -> str:
    """Read's line-number-prefixed rendering of a whole file."""
    return "\n".join(f"{n:>6}\t{line}" for n, line in enumerate(content.splitlines(), 1))


# --------------------------------------------------------------------------
# Driving the real hook
# --------------------------------------------------------------------------


def drive_hook(action: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    """Run ``neuralmind _hook <action>`` in-process; return its JSON response."""
    from neuralmind.hooks import run_hook

    saved_in, saved_out = sys.stdin, sys.stdout
    sys.stdin = io.StringIO(json.dumps(payload))
    sys.stdout = captured = io.StringIO()
    try:
        run_hook(action)
    finally:
        sys.stdin, sys.stdout = saved_in, saved_out
    out = captured.getvalue().strip()
    if not out:
        return None
    try:
        return json.loads(out)
    except ValueError:
        # Hook stdout must be only the JSON object. Anything else is a
        # non-blocking hook error, and PostToolUse plain stdout goes to the
        # debug log, so nothing from this response reaches Claude.
        return {"_invalid_json": True}


def _bash_shape_ok(value: Any) -> bool:
    return isinstance(value, dict) and all(k in value for k in ("stdout", "stderr", "interrupted"))


def _read_shape_ok(value: Any) -> bool:
    f = value.get("file") if isinstance(value, dict) else None
    return (
        isinstance(value, dict)
        and value.get("type") == "text"
        and isinstance(f, dict)
        and all(k in f for k in ("filePath", "content", "numLines", "startLine", "totalLines"))
    )


def _grep_shape_ok(value: Any) -> bool:
    return isinstance(value, dict) and all(k in value for k in ("numFiles", "filenames"))


def apply_response(
    tool: str, result: str, response: dict[str, Any] | None, **ctx: Any
) -> tuple[str, str]:
    """What reaches Claude after the hook: (tool result, added context)."""
    if not response or response.get("_invalid_json"):
        return result, ""
    out = response.get("hookSpecificOutput") or {}
    replaced = out.get("updatedToolOutput")
    if replaced is not None:
        if tool == "Bash" and _bash_shape_ok(replaced):
            result, _ = bash_result(
                replaced.get("stdout", ""), replaced.get("stderr", ""), 0, ctx.get("command", "")
            )
        elif tool == "Read" and _read_shape_ok(replaced):
            result = read_result(replaced["file"]["content"])
        elif tool == "Grep" and _grep_shape_ok(replaced):
            result = replaced.get("content") or "\n".join(replaced.get("filenames", []))
        # Otherwise the shape doesn't match and Claude Code ignores it.
    context = out.get("additionalContext") or ""
    return result, _overflow(context, ADDITIONAL_CONTEXT_CAP, "hook-context")


# --------------------------------------------------------------------------
# Retention
# --------------------------------------------------------------------------


def _kept_share(needed: list[str], delivered: str) -> float | None:
    """Share of ``needed`` lines that appear verbatim in ``delivered``."""
    if not needed:
        return None
    lines = set(delivered.splitlines())
    return sum(1 for ln in needed if ln in lines) / len(needed)


def _definitions(source: str) -> list[str]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    return [
        n.name
        for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    ]


def _names_kept(names: list[str], delivered: str) -> float | None:
    if not names:
        return None
    return sum(1 for n in names if re.search(rf"\b{re.escape(n)}\b", delivered)) / len(names)


def _source_lines_kept(source: str, delivered: str) -> float | None:
    """Share of non-blank source lines whose text survives in ``delivered``."""
    lines = [ln.strip() for ln in source.splitlines() if ln.strip()]
    if not lines:
        return None
    body = delivered
    return sum(1 for ln in lines if ln in body) / len(lines)


# --------------------------------------------------------------------------
# The three tools
# --------------------------------------------------------------------------


def _digest(*parts: str) -> str:
    """Fingerprint of exactly what an arm delivers, independent of the tokenizer."""
    return hashlib.sha256("\x00".join(parts).encode("utf-8")).hexdigest()


def _hook_fields(response: dict[str, Any] | None) -> dict[str, bool]:
    return {
        "hook_fired": response is not None,
        "hook_json_valid": response is None or not response.get("_invalid_json", False),
    }


def _pct(after: int, before: int) -> float | None:
    return None if before == 0 else round(100.0 * (after - before) / before, 1)


def bash_samples(corpus_dir: Path, cwd: Path) -> list[dict[str, Any]]:
    from neuralmind.compressors import compress_bash

    manifest = json.loads((corpus_dir / "manifest.json").read_text(encoding="utf-8"))
    rows = []
    for entry in manifest["entries"]:
        stdout = (corpus_dir / entry["stdout_file"]).read_text(encoding="utf-8")
        stderr = ""
        if entry.get("stderr_file"):
            stderr = (corpus_dir / entry["stderr_file"]).read_text(encoding="utf-8")
        command, exit_code = entry["command"], entry["exit_code"]
        baseline, valid = bash_result(stdout, stderr, exit_code, command)

        # PostToolUse fires only for a valid result; a failure goes to
        # PostToolUseFailure, where NeuralMind registers nothing.
        response = None
        if valid:
            payload = {
                "hook_event_name": "PostToolUse",
                "cwd": str(cwd),
                "tool_name": "Bash",
                "tool_input": {"command": command},
                # BashOutput carries no exit code: the hook always sees 0.
                "tool_response": {
                    "stdout": stdout,
                    "stderr": stderr,
                    "interrupted": False,
                    "isImage": False,
                },
            }
            response = drive_hook("compress-bash", payload)
        result, context = apply_response("Bash", baseline, response, command=command)

        # The compressor on its own terms: what a replacing hook would deliver
        # for this call (valid results), or what it would have produced for a
        # failure that no PostToolUse hook can reach.
        compressed = compress_bash(stdout, stderr, 0 if valid else exit_code)
        if valid:
            compressed, _ = bash_result(compressed, "", 0, command)

        needed = [
            ln
            for ln in _join_streams(stdout, stderr).splitlines()
            if any(re.search(p, ln) for p in entry["must_keep"])
        ]
        rows.append(
            {
                "tool": "Bash",
                "id": entry["id"],
                "category": entry["category"],
                "command": command,
                "exit_code": exit_code,
                "event": "PostToolUse" if valid else "PostToolUseFailure",
                **_hook_fields(response),
                "baseline_tokens": count_tokens(baseline),
                "as_shipped_tokens": count_tokens(result) + count_tokens(context),
                "added_context_tokens": count_tokens(context),
                "compressor_only_tokens": count_tokens(compressed),
                "as_shipped_sha256": _digest(result, context),
                "compressor_only_sha256": _digest(compressed),
                "compressor_reachable": valid,
                "must_keep_lines": len(needed),
                "must_keep_kept": _kept_share(needed, compressed),
            }
        )
    return rows


def _repo_sources(src: Path) -> list[Path]:
    return sorted(p for p in src.rglob("*.py") if ".neuralmind" not in p.parts)


def read_samples(repo: str, src: Path, nm: Any, cwd: Path) -> list[dict[str, Any]]:
    from neuralmind.compressors import compress_read

    rows = []
    for path in _repo_sources(src):
        content = path.read_text(encoding="utf-8")
        baseline = read_result(content)
        n = len(content.splitlines())
        payload = {
            "hook_event_name": "PostToolUse",
            "cwd": str(cwd),
            "tool_name": "Read",
            "tool_input": {"file_path": str(path)},
            "tool_response": {
                "type": "text",
                "file": {
                    "filePath": str(path),
                    "content": content,
                    "numLines": n,
                    "startLine": 1,
                    "totalLines": n,
                },
            },
        }
        response = drive_hook("compress-read", payload)
        result, context = apply_response("Read", baseline, response)

        # The compressor as designed: given the text, with the index loaded.
        compressed = compress_read(str(path), baseline, mind=nm)
        defs = _definitions(content)
        rows.append(
            {
                "tool": "Read",
                "id": f"{repo}/{path.relative_to(src).as_posix()}",
                "category": repo,
                **_hook_fields(response),
                "baseline_tokens": count_tokens(baseline),
                "as_shipped_tokens": count_tokens(result) + count_tokens(context),
                "added_context_tokens": count_tokens(context),
                "compressor_only_tokens": count_tokens(compressed),
                "as_shipped_sha256": _digest(result, context),
                "compressor_only_sha256": _digest(compressed),
                "compressor_reachable": True,
                "compressed": compressed != baseline,
                "definitions": len(defs),
                "definitions_kept": _names_kept(defs, compressed),
                "source_lines_kept": _source_lines_kept(content, compressed),
            }
        )
    return rows


def _oracle_identifiers(repo: dict[str, Any]) -> list[str]:
    names = []
    for q in repo["queries"]:
        m = re.search(r"(?:class|def)\s+(\w+)", q.get("oracle_symbol", ""))
        if m and m.group(1) not in names:
            names.append(m.group(1))
    return names


def _grep(src: Path, pattern: str) -> tuple[list[str], list[str]]:
    """ripgrep-style content lines and matching files, sorted by path."""
    rx = re.compile(pattern)
    lines, files = [], []
    for path in _repo_sources(src):
        rel = path.relative_to(src).as_posix()
        hit = False
        for n, text in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if rx.search(text):
                lines.append(f"{rel}:{n}:{text}")
                hit = True
        if hit:
            files.append(rel)
    return lines, files


def grep_samples(repo: dict[str, Any], src: Path, cwd: Path) -> list[dict[str, Any]]:
    from neuralmind.compressors import cap_search_results

    patterns = [rf"\b{name}\b" for name in _oracle_identifiers(repo)] + BROAD_PATTERNS
    rows = []
    for pattern in patterns:
        lines, files = _grep(src, pattern)
        if not lines:
            continue
        for mode in ("content", "files_with_matches"):
            if mode == "content":
                shown = lines[:GREP_HEAD_LIMIT]
                baseline = "\n".join(shown)
                response_obj = {
                    "mode": "content",
                    "numFiles": len(files),
                    "filenames": files,
                    "content": baseline,
                    "numLines": len(shown),
                }
                compressed = cap_search_results(baseline)
                shown_set = set(shown)
                kept = sum(1 for ln in compressed.splitlines() if ln in shown_set)
                needed = len(shown)
            else:
                baseline = "\n".join(files)
                response_obj = {
                    "mode": "files_with_matches",
                    "numFiles": len(files),
                    "filenames": files,
                }
                compressed = baseline  # the hook reads no content in this mode
                kept = needed = len(files)
            payload = {
                "hook_event_name": "PostToolUse",
                "cwd": str(cwd),
                "tool_name": "Grep",
                "tool_input": {"pattern": pattern, "output_mode": mode},
                "tool_response": response_obj,
            }
            response = drive_hook("cap-search", payload)
            result, context = apply_response("Grep", baseline, response)
            rows.append(
                {
                    "tool": "Grep",
                    "id": f"{repo['name']}:{mode}:{pattern}",
                    "category": mode,
                    **_hook_fields(response),
                    "baseline_tokens": count_tokens(baseline),
                    "as_shipped_tokens": count_tokens(result) + count_tokens(context),
                    "added_context_tokens": count_tokens(context),
                    "compressor_only_tokens": count_tokens(compressed),
                    "as_shipped_sha256": _digest(result, context),
                    "compressor_only_sha256": _digest(compressed),
                    "compressor_reachable": True,
                    "matches_shown": needed,
                    "matches_kept": None if not needed else kept / needed,
                }
            )
    return rows


# --------------------------------------------------------------------------
# Aggregation and report
# --------------------------------------------------------------------------


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    base = sum(r["baseline_tokens"] for r in rows)
    shipped = sum(r["as_shipped_tokens"] for r in rows)
    reach = [r for r in rows if r["compressor_reachable"]]
    reach_base = sum(r["baseline_tokens"] for r in reach)
    reach_comp = sum(r["compressor_only_tokens"] for r in reach)
    per_call = [_pct(r["as_shipped_tokens"], r["baseline_tokens"]) for r in rows]
    per_call = [p for p in per_call if p is not None]
    comp_calls = [_pct(r["compressor_only_tokens"], r["baseline_tokens"]) for r in reach]
    comp_calls = [p for p in comp_calls if p is not None]
    return {
        "calls": len(rows),
        "hook_fired": sum(1 for r in rows if r["hook_fired"]),
        "baseline_tokens": base,
        "as_shipped_tokens": shipped,
        "as_shipped_change_pct": _pct(shipped, base),
        "as_shipped_per_call_pct": _spread(per_call),
        "compressor_reachable_calls": len(reach),
        "compressor_only_tokens": reach_comp,
        "compressor_only_change_pct": _pct(reach_comp, reach_base),
        "compressor_only_per_call_pct": _spread(comp_calls),
    }


def _spread(values: list[float]) -> dict[str, float] | None:
    if not values:
        return None
    return {
        "mean": round(statistics.fmean(values), 1),
        "median": round(statistics.median(values), 1),
        "min": min(values),
        "max": max(values),
    }


def _mean(values: list[float | None]) -> float | None:
    vals = [v for v in values if v is not None]
    return None if not vals else round(statistics.fmean(vals), 3)


def _corpus_digest(corpus_dir: Path) -> str:
    # Text mode, so a checkout with CRLF line endings (git on Windows) hashes
    # the same as the LF files the corpus was captured as.
    h = hashlib.sha256()
    for path in sorted(corpus_dir.iterdir()):
        h.update(path.name.encode())
        h.update(path.read_text(encoding="utf-8").encode("utf-8"))
    return h.hexdigest()


def run(work_dir: Path, corpus_dir: Path = CORPUS_DIR) -> dict[str, Any]:
    stray = [k for k in _THRESHOLD_ENV if k in os.environ]
    if stray:
        raise SystemExit(f"unset {', '.join(stray)}: the benchmark measures the default thresholds")

    from neuralmind import __version__, compressors

    manifest = load_manifest()
    rows: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="nm-compression-cwd-") as cwd:
        rows += bash_samples(corpus_dir, Path(cwd))
        for repo in manifest["repos"]:
            src = ensure_checkout(repo, work_dir)
            if src is None:
                raise SystemExit(f"could not check out {repo['name']} at its pinned commit")
            with contextlib.redirect_stdout(sys.stderr):
                nm = _build_nm(src)
            if nm is None:
                raise SystemExit(f"could not build a NeuralMind index for {repo['name']}")
            rows += read_samples(repo["name"], src, nm, Path(cwd))
            rows += grep_samples(repo, src, Path(cwd))

    by_tool = {tool: [r for r in rows if r["tool"] == tool] for tool in ("Read", "Bash", "Grep")}
    # Per tool only: a total across tools would be weighted by an arbitrary
    # mix of calls and mean nothing.
    summary = {tool: _summarize(tool_rows) for tool, tool_rows in by_tool.items()}
    small = [r for r in by_tool["Read"] if r["baseline_tokens"] <= READ_PAGE_SENSITIVITY]
    summary["Read"]["compressor_only_change_pct_excluding_large_files"] = _summarize(small)[
        "compressor_only_change_pct"
    ]
    summary["Read"]["large_files_excluded_from_that_figure"] = len(by_tool["Read"]) - len(small)
    summary["Read"]["per_repo"] = {
        repo: {
            **_summarize([r for r in by_tool["Read"] if r["category"] == repo]),
            "definitions_kept_mean": _mean(
                [
                    r["definitions_kept"]
                    for r in by_tool["Read"]
                    if r["category"] == repo and r["compressed"]
                ]
            ),
            "source_lines_kept_mean": _mean(
                [
                    r["source_lines_kept"]
                    for r in by_tool["Read"]
                    if r["category"] == repo and r["compressed"]
                ]
            ),
        }
        for repo in sorted({r["category"] for r in by_tool["Read"]})
    }
    summary["Grep"]["per_mode"] = {
        mode: _summarize([r for r in by_tool["Grep"] if r["category"] == mode])
        for mode in ("content", "files_with_matches")
    }
    reads = [r for r in by_tool["Read"] if r["compressed"]]
    summary["Read"]["compressed_files"] = len(reads)
    summary["Read"]["definitions_kept_mean"] = _mean([r["definitions_kept"] for r in reads])
    summary["Read"]["source_lines_kept_mean"] = _mean([r["source_lines_kept"] for r in reads])
    bash_reach = [r for r in by_tool["Bash"] if r["compressor_reachable"]]
    bash_fail = [r for r in by_tool["Bash"] if not r["compressor_reachable"]]
    summary["Bash"]["must_keep_kept_mean_reachable"] = _mean(
        [r["must_keep_kept"] for r in bash_reach]
    )
    summary["Bash"]["must_keep_kept_mean_failures"] = _mean(
        [r["must_keep_kept"] for r in bash_fail]
    )
    content = [r for r in by_tool["Grep"] if r["category"] == "content"]
    summary["Grep"]["content_mode_matches_kept_mean"] = _mean([r["matches_kept"] for r in content])

    return {
        "meta": {
            "generated": date.today().isoformat(),
            "neuralmind_version": __version__,
            "tokenizer": tokenizer_name(),
            "tool_response_shapes": SDK_SHAPES,
            "protocol_docs": DOCS,
            "protocol_docs_read_on": DOCS_READ_ON,
            "protocol": {
                "additional_context_cap_chars": ADDITIONAL_CONTEXT_CAP,
                "overflow_preview_chars": OVERFLOW_PREVIEW,
                "bash_valid_inline_chars": BASH_VALID_INLINE,
                "bash_failure_inline_chars": BASH_FAILURE_INLINE,
                "grep_head_limit": GREP_HEAD_LIMIT,
                "read_sensitivity_tokens": READ_PAGE_SENSITIVITY,
            },
            "compressor_thresholds": {
                "bash_max_chars": compressors.BASH_MAX_CHARS,
                "bash_small_passthrough": compressors.BASH_SMALL_PASSTHROUGH,
                "bash_tail_lines": compressors.BASH_TAIL_LINES,
                "search_max_matches": compressors.SEARCH_MAX_MATCHES,
                "read_min_chars": 1500,
            },
            "pinned_repos": {r["name"]: r["commit"] for r in manifest["repos"]},
            "bash_corpus_sha256": _corpus_digest(corpus_dir),
        },
        "summary": summary,
        "samples": rows,
    }


def _fmt_pct(p: float | None) -> str:
    return "—" if p is None else f"{p:+.1f}%"


def _fmt_share(p: float | None) -> str:
    return "—" if p is None else f"{100 * p:.0f}%"


def render_markdown(report: dict[str, Any]) -> str:
    s, meta = report["summary"], report["meta"]
    samples = report["samples"]

    def reach_base(rows: list[dict[str, Any]]) -> int:
        return sum(x["baseline_tokens"] for x in rows if x["compressor_reachable"])

    out = [
        "# Tool-output compression benchmark",
        "",
        (
            f"Generated {meta['generated']} with NeuralMind {meta['neuralmind_version']} · "
            f"tokenizer: {meta['tokenizer']} · tool_response shapes: {meta['tool_response_shapes']} · "
            f"hook protocol per {', '.join(meta['protocol_docs'])} (read {meta['protocol_docs_read_on']})."
        ),
        "",
        (
            "Reproduce: `python -m evals.compression.run --out bench/compression`. Method and caveats: "
            "[docs/benchmarks/compression.md](../../docs/benchmarks/compression.md)."
        ),
        "",
        "## What Claude sees with the hooks installed",
        "",
        "| Tool call | Calls | Hook responded | Tokens, no hook | Tokens, hooks as shipped | Change |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    rows = [
        ("Read (whole file)", s["Read"]),
        ("Bash", s["Bash"]),
        ("Grep, content mode", s["Grep"]["per_mode"]["content"]),
        ("Grep, files_with_matches (default)", s["Grep"]["per_mode"]["files_with_matches"]),
    ]
    for label, t in rows:
        out.append(
            f"| {label} | {t['calls']} | {t['hook_fired']} | {t['baseline_tokens']:,} | "
            f"{t['as_shipped_tokens']:,} | {_fmt_pct(t['as_shipped_change_pct'])} |"
        )
    invalid = sum(1 for x in samples if not x.get("hook_json_valid", True))
    if invalid:
        out += [
            "",
            f"{invalid} hook responses were not valid JSON and were treated as having no effect.",
        ]
    r, b, g = s["Read"], s["Bash"], s["Grep"]
    reads = [x for x in samples if x["tool"] == "Read"]
    bashes = [x for x in samples if x["tool"] == "Bash"]
    greps = [x for x in samples if x["tool"] == "Grep" and x["category"] == "content"]
    out += [
        "",
        "## What the compressors produce (hypothetical: delivered instead of the result)",
        "",
        "| Tool call | Calls a replacing hook could reach | Tokens, no hook | Tokens, compressor output | Change | What survives |",
        "|---|---:|---:|---:|---:|---|",
        (
            f"| Read (whole file) | {r['compressor_reachable_calls']} ({r['compressed_files']} over 1,500 chars) | "
            f"{reach_base(reads):,} | {r['compressor_only_tokens']:,} | {_fmt_pct(r['compressor_only_change_pct'])} | "
            f"{_fmt_share(r['definitions_kept_mean'])} of definitions named, "
            f"{_fmt_share(r['source_lines_kept_mean'])} of source lines |"
        ),
        (
            f"| Bash | {b['compressor_reachable_calls']} of {b['calls']} | {reach_base(bashes):,} | "
            f"{b['compressor_only_tokens']:,} | {_fmt_pct(b['compressor_only_change_pct'])} | "
            f"{_fmt_share(b['must_keep_kept_mean_reachable'])} of must-keep lines |"
        ),
        (
            f"| Grep, content mode | {g['per_mode']['content']['compressor_reachable_calls']} | {reach_base(greps):,} | "
            f"{g['per_mode']['content']['compressor_only_tokens']:,} | "
            f"{_fmt_pct(g['per_mode']['content']['compressor_only_change_pct'])} | "
            f"{_fmt_share(g['content_mode_matches_kept_mean'])} of matches |"
        ),
        "",
        (
            f"Read, excluding the {r['large_files_excluded_from_that_figure']} files whose whole-file result is over "
            f"{meta['protocol']['read_sensitivity_tokens']:,} tokens (Claude Code may page those): "
            f"{_fmt_pct(r['compressor_only_change_pct_excluding_large_files'])}."
        ),
        "",
        "### Read, per repo",
        "",
        "| Repo | Files | Hook responded | Compressor output vs. no hook | Definitions named | Source lines kept |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for repo, t in r["per_repo"].items():
        out.append(
            f"| {repo} | {t['calls']} | {t['hook_fired']} | {_fmt_pct(t['compressor_only_change_pct'])} | "
            f"{_fmt_share(t['definitions_kept_mean'])} | {_fmt_share(t['source_lines_kept_mean'])} |"
        )
    out += [
        "",
        "## Bash, per command",
        "",
        "| Command | Exit | Event | Hook responded | No hook | As shipped | Compressor only | Must-keep kept |",
        "|---|---:|---|:---:|---:|---:|---:|---:|",
    ]
    for x in bashes:
        out.append(
            f"| `{x['id']}` ({x['category']}) | {x['exit_code']} | {x['event']} | "
            f"{'yes' if x['hook_fired'] else 'no'} | {x['baseline_tokens']:,} | "
            f"{x['as_shipped_tokens']:,} ({_fmt_pct(_pct(x['as_shipped_tokens'], x['baseline_tokens']))}) | "
            f"{x['compressor_only_tokens']:,}{'' if x['compressor_reachable'] else ' †'} | "
            f"{_fmt_share(x['must_keep_kept'])} |"
        )
    out += [
        "",
        (
            "† A failed command fires PostToolUseFailure, which cannot replace the result; "
            "the figure is what the compressor would have produced had anything been able to deliver it."
        ),
        "",
    ]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="NeuralMind tool-output compression benchmark")
    ap.add_argument(
        "--work-dir", default=".bench-work", help="where the pinned repos are checked out"
    )
    ap.add_argument("--out", default=None, help="write results.json + report.md under this dir")
    ap.add_argument("--json", action="store_true", help="print the summary as JSON")
    args = ap.parse_args(argv)
    report = run(Path(args.work_dir))
    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / "results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        (out / "report.md").write_text(render_markdown(report), encoding="utf-8")
    if args.json:
        print(json.dumps(report["summary"], indent=2))
    else:
        print(render_markdown(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
