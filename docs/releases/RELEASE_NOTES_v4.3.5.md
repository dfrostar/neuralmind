# NeuralMind v4.3.5

**Date:** 2026-09-28 | **Type:** Patch release

The Read, Bash and Grep PostToolUse hooks stop adding tokens. For years they
were described as compressing tool output "before the agent sees it". A new
benchmark that follows Claude Code's documented hook protocol shows they never
did: Claude Code **adds** a hook's `additionalContext` next to the tool result
rather than replacing it, so Claude got the full output *plus* NeuralMind's
compressed copy.

## What the benchmark found (v4.3.4)

| Tool call | Calls | Tokens, no hook | Tokens, v4.3.4 hooks | Change |
|---|---:|---:|---:|---:|
| Read (whole file) | 136 | 597,002 | 597,002 | +0.0% |
| Bash | 16 | 32,581 | 38,296 | +17.5% |
| Grep, content mode | 48 | 55,800 | 68,113 | +22.1% |
| Grep, files_with_matches (default) | 48 | 2,062 | 2,062 | +0.0% |

- **Bash:** every successful command got a second copy. It was the whole output
  again when nothing was compressed (`pip list`, a short `pytest -q`: +100%), and
  errors plus the tail when it was.
- **Read:** the hook never fired. Claude Code's Read payload nests the text
  under `file.content`, which the hook didn't read.
- **Failed commands** fire `PostToolUseFailure`, not `PostToolUse`, so the Bash
  hook never saw a failing test run, lint error or crash. Those are the outputs
  its "errors + summary" design was built for.

Method, per-command results and raw data:
[docs/benchmarks/compression.md](../benchmarks/compression.md) ·
`bench/compression/results-v4.3.4.json`.

## What changed

- `neuralmind _hook compress-read`, `compress-bash`, `cap-search` and `offload`
  return nothing. Claude sees exactly the tool result.
- The Bash hook still writes each command's raw output to
  `.neuralmind/last_output.json`, so `neuralmind last` works as before.
- Every other hook is unchanged: session memory (SessionStart), prompt-time
  recall (UserPromptSubmit), the stale-decision guard (PreToolUse), reuse
  feedback (PostToolUse on Edit/Write), and the session digest (Stop,
  SessionEnd).

## What the agent actually sees after upgrading

| Agent | Before (v4.3.4) | After (v4.3.5) |
|---|---|---|
| Claude Code | Bash and content-mode Grep results followed by a system reminder holding NeuralMind's copy of the same output | The tool result alone |
| Cursor, Cline, Continue, Codex, any MCP client | Unaffected: these hooks are Claude Code-only | Unaffected |

## Do I need to do anything?

No. Upgrade the package; the registered hooks are the same, so there is no need
to re-run `neuralmind install-hooks`.

## Not changed

- The compressor functions (`compress_bash`, `compress_read`,
  `cap_search_results`, `offload_if_large`) stay in the Python API. The
  benchmark measures them too: they would cut 66–89% of tokens if they replaced
  a result, but keep only 6% of a file's source lines and 0% of a diff's
  changed lines. That is why nothing replaces tool output until a design keeps
  what the agent needs, measured by the same benchmark.
- `NEURALMIND_BASH_TAIL`, `NEURALMIND_BASH_MAX_CHARS` and `NEURALMIND_BASH_SMALL`
  now only tune those Python functions. `NEURALMIND_BYPASS=1` still switches off
  every NeuralMind hook action.

## New in the repo

- `evals/compression/`: the benchmark. It drives the real hook with payloads
  shaped like Claude Code's (Agent SDK `sdk-tools.d.ts`) and applies each
  response per the documented protocol. The Bash corpus is 16 real command
  outputs with pre-registered must-keep lines.
- `tests/test_compression_benchmark.py`: recomputes the Bash results on every
  CI run and fails if the hooks stop doing what `bench/compression/results.json`
  records, or if the benchmark page stops quoting it.
- Docs, README, site and `llms.txt` no longer describe tool-output compression
  as a feature.
