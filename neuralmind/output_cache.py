"""
output_cache.py — Single-slot cache of the most recent bash output
==================================================================

When NeuralMind compresses a Bash tool output, the stdout/stderr is
stashed to ``<project>/.neuralmind/last_output.json`` so an agent can
recover the dropped middle without re-running the command. It is
**credential-scrubbed** on the way in and again on the way out — see
"Redacted" below; nothing here writes raw command output to disk. This turns
``NEURALMIND_BYPASS=1`` from a "re-run from scratch" escape hatch into
a free lookup for the common "wait, I need to see what was elided"
pattern — which is what costs real time on expensive commands like
``npm test`` (~28s) or non-deterministic network calls.

Design:
- **One slot.** Most recent only. We're not building a journal.
- **Size-capped.** Defaults to 2 MB total; oversize payloads are split
  proportionally between stdout/stderr and truncated keeping head+tail
  so the error-bearing tail survives.
- **Atomic writes.** Temp-file + rename so concurrent hook invocations
  can't leave a half-written cache behind.
- **Redacted.** Credentials are stripped before the payload touches
  disk (``neuralmind.secret_scan``). The cache records whatever a
  command printed, so ``printenv``, ``aws configure list``, or a curl
  with an ``Authorization`` header would otherwise land a live key in
  a plaintext file. Opt out with ``NEURALMIND_OUTPUT_REDACT=0``.
- **Fail-open.** Cache failures never disrupt the hook; they just
  leave ``neuralmind last`` empty.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path

from .secret_scan import redact_text
from .state_dir import ensure_state_dir

CACHE_FILENAME = "last_output.json"
DEFAULT_MAX_BYTES = int(os.environ.get("NEURALMIND_OUTPUT_CACHE_MAX", str(2 * 1024 * 1024)))


def cache_path(project_path: str | Path) -> Path:
    """Resolve the cache file location for a project."""
    return Path(project_path).resolve() / ".neuralmind" / CACHE_FILENAME


def _truncate_keep_ends(text: str, budget: int) -> str:
    """Truncate a string keeping head + tail, with an elision marker.

    The tail is where errors usually live — keep it verbatim.
    """
    if len(text) <= budget or budget <= 0:
        return text
    keep = budget // 2
    head = text[:keep]
    tail = text[-(budget - keep) :]
    dropped = len(text) - len(head) - len(tail)
    return head + f"\n\n[... {dropped} bytes elided by output cache ...]\n\n" + tail


def write_last_output(
    project_path: str | Path,
    stdout: str,
    stderr: str,
    exit_code: int,
    command: str = "",
    max_bytes: int | None = None,
) -> Path | None:
    """Persist the last bash output for ``neuralmind last`` recovery.

    Returns the cache path on success, ``None`` on failure or when the
    cache is disabled via ``NEURALMIND_OUTPUT_CACHE=0``.
    """
    if os.environ.get("NEURALMIND_OUTPUT_CACHE") == "0":
        return None

    # Strip credentials *before* truncation so a secret can never survive
    # in a kept head/tail slice, and before the size math so the budget is
    # computed against what actually gets written.
    redacted_kinds: list[str] = []
    if os.environ.get("NEURALMIND_OUTPUT_REDACT") != "0":
        stdout, out_hits = redact_text(stdout)
        stderr, err_hits = redact_text(stderr)
        command, cmd_hits = redact_text(command)
        redacted_kinds = sorted({m.kind for m in (*out_hits, *err_hits, *cmd_hits)})

    cap = max_bytes if max_bytes is not None else DEFAULT_MAX_BYTES
    total = len(stdout) + len(stderr)
    if total > cap:
        # Split budget proportionally; floor each side at 1 KB so a
        # 99% stderr / 1% stdout payload still leaves room for the
        # smaller stream's framing.
        if stdout and stderr:
            stdout_budget = max(1024, int(cap * len(stdout) / total))
            stderr_budget = max(1024, cap - stdout_budget)
        elif stdout:
            stdout_budget, stderr_budget = cap, 0
        else:
            stdout_budget, stderr_budget = 0, cap
        stdout = _truncate_keep_ends(stdout, stdout_budget)
        stderr = _truncate_keep_ends(stderr, stderr_budget)

    payload = {
        "ts": time.time(),
        "command": command[:500] if command else "",
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        # Surfaced by `neuralmind last` so a developer knows the output was
        # scrubbed and can re-run the command themselves if they need it.
        "redacted": redacted_kinds,
    }

    try:
        target = cache_path(project_path)
        # ensure_state_dir also drops the self-ignoring .gitignore, so the
        # cache cannot be committed even if this is the first thing that
        # ever creates .neuralmind/ in the project.
        ensure_state_dir(project_path)
        # Atomic write: temp-file in same dir, then rename.
        fd, tmp = tempfile.mkstemp(prefix=".last_output.", suffix=".tmp", dir=str(target.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(payload, f)
            os.replace(tmp, target)
            return target
        except Exception:
            # Best-effort cleanup if the rename never happened.
            try:
                os.unlink(tmp)
            except OSError:
                pass
            return None
    except Exception:
        return None


def read_last_output(project_path: str | Path) -> dict | None:
    """Return the most recent cached bash output, or ``None`` if missing.

    Redacts on the way out as well as on the way in. A cache written by a
    version from before redaction existed is plaintext on disk, and an
    upgrade does not rewrite it — so without this, the first
    ``neuralmind last`` after upgrading would hand back the very credential
    the upgrade was meant to protect. Scrubbing here is idempotent: text
    already redacted at write time has nothing left to find.

    Honours the same ``NEURALMIND_OUTPUT_REDACT=0`` opt-out as the writer.
    """
    try:
        text = cache_path(project_path).read_text(encoding="utf-8")
        data = json.loads(text)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    if not isinstance(data, dict) or "stdout" not in data:
        return None

    if os.environ.get("NEURALMIND_OUTPUT_REDACT") == "0":
        return data

    kinds: set[str] = set(data.get("redacted") or [])
    for field in ("stdout", "stderr", "command"):
        value = data.get(field)
        if not isinstance(value, str) or not value:
            continue
        scrubbed, hits = redact_text(value)
        if hits:
            data[field] = scrubbed
            kinds.update(m.kind for m in hits)
    data["redacted"] = sorted(kinds)
    return data
