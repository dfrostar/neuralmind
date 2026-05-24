# NeuralMind v0.10.0 — agent ergonomics

**Release Date:** May 2026

## TL;DR

Three friction-removing changes to the PostToolUse Bash compressor —
the surface AI agents see on every shell call. Built from real
session feedback where the previous footer forced a second query
round-trip on dropped middle content.

- **Show what was dropped.** The footer below every compressed Bash
  output now categorizes the elided lines (info/debug/warn/other
  counts plus repeated-line detection) instead of just reporting
  byte totals. Agents can judge whether the dropped middle was
  12 winston INFO lines (fine) or a buried error (worth recovering)
  without re-running the command.
- **`neuralmind last`** — new CLI that surfaces the raw pre-compression
  output stashed by the hook in `<project>/.neuralmind/last_output.json`.
  Turns `NEURALMIND_BYPASS=1` from a re-run-from-scratch escape hatch
  into a free lookup — meaningful on expensive commands (`npm test`
  ~28s) and non-deterministic network calls.
- **Small-failure passthrough.** A failing 50-byte command no longer
  gets buried under a 200-byte compression marker. Outputs under
  `NEURALMIND_BASH_SMALL` (default 500 chars) pass through verbatim
  with just exit-code framing, even on non-zero exit.

No migration. Same `graph.json`, same `synapses.db`, same hooks. The
new cache file is additive — disable via `NEURALMIND_OUTPUT_CACHE=0`
if you don't want it.

---

## What the agent actually sees, post-install

The single most-visible surface NeuralMind exposes to *every* AI
coding agent is the PostToolUse Bash footer. Pre-v0.10.0 it said:

```
[Full output: 4298 bytes stdout + 0 bytes stderr.
 Re-run with NEURALMIND_BYPASS=1 env var to see everything.]
```

That tells you *how much* was dropped, not *what*. v0.10.0 makes it
content-aware:

```
[neuralmind: dropped 23 lines (12 info, 8 debug, 3 other);
 repeated: 5× 'Gamma API error 503'  ·  4298 B stdout total  ·
 `neuralmind last` for cached raw  ·  NEURALMIND_BYPASS=1 to disable]
```

The categorizer recognizes log-level prefixes from winston, python
logging, rust env_logger, go-kit, and similar structured loggers.
Repeated patterns (5+ occurrences of the same line) are surfaced
distinctly so an agent reading test/log output can tell apart noise
from signal.

### Per-agent expectations

| Agent | What it sees | What it can do |
|-------|--------------|----------------|
| **Claude Code** | New footer on every Bash tool call (PostToolUse hook). Categorized "dropped" summary and `neuralmind last` affordance. | Run `neuralmind last` via Bash to recover the cached raw output without re-running the original command. |
| **Cursor / Cline / Continue** | Same MCP server as before (unchanged). The Bash footer applies only when the PostToolUse hook is installed via `neuralmind install-hooks --global`. | Same recovery path via `neuralmind last`. |
| **Any other MCP client** | MCP toolset unchanged. The recovery cache is available to *any* agent that can run the `neuralmind` CLI. | Same. |

---

## `neuralmind last` — recovery without re-running

```bash
# Human-readable raw output (what the agent would have seen pre-compression).
neuralmind last

# Full payload (timestamp, command, exit code, stdout, stderr) as JSON.
neuralmind last --json
```

The hook writes `<project>/.neuralmind/last_output.json` on every
Bash tool call. **Single-slot cache** (most recent only — not a
journal). **2 MB default cap**; oversize payloads are split
proportionally between stdout/stderr and truncated keeping head +
tail so the error-bearing tail survives verbatim. **Atomic writes**
via temp-file + rename so concurrent hook invocations can't leave
a half-written cache behind. **Fail-open**: cache write failures
never disrupt the hook.

Tunable knobs:

| Env var | Default | Effect |
|---------|---------|--------|
| `NEURALMIND_OUTPUT_CACHE` | `1` | Set to `0` to disable the cache entirely. |
| `NEURALMIND_OUTPUT_CACHE_MAX` | `2097152` (2 MB) | Total size cap in bytes. Oversize splits head+tail. |
| `NEURALMIND_BASH_SMALL` | `500` | Outputs under this many chars pass through verbatim even on non-zero exit. |

---

## Why this matters

The compressor is the *most-visible* surface NeuralMind exposes —
the agent sees it on every Bash call. Pre-v0.10.0 the footer was
generic (byte counts), the recovery path was expensive (re-run the
command), and tiny failures got buried under marker overhead. This
release converts the common "I need to see the dropped middle"
friction from a re-run loop into a single cache lookup, and turns
the footer text itself into actionable messaging — concrete benefit
visible, concrete affordance, clear escape hatch.

Not in this release (each deserves its own ship):

- Type-aware compression (diff/JSON/test specialization)
- Synapse recall markers (surface the differentiated value at the
  agent layer the way the bash compressor does today)
- `neuralmind status` health check
- Incremental graph updates for large repos

---

## Upgrade

Same as every prior minor release — install path's `--upgrade`
equivalent:

```bash
pip install --upgrade neuralmind
# or
pipx upgrade neuralmind
# or
uv pip install --upgrade neuralmind
# or
docker pull ghcr.io/dfrostar/neuralmind:latest
```

No graph rebuild needed. No synapse store migration. Hooks installed
from earlier releases continue to work; reinstall (`neuralmind
install-hooks`) only if you want the v0.10.0 marker text in already-
configured `.claude/settings.json` — the runtime behavior comes from
the upgraded package, not the settings entry.
