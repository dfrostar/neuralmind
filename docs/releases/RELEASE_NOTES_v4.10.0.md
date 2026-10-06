# NeuralMind v4.10.0

**Date:** 2026-10-06 | **Type:** Minor release (one opt-in feature)

An opt-in mode in which a PostToolUse hook replaces tool output rather than
adding to it, for one kind of output only: the progress lines of an install or
an index build. It is off by default, and the
[compression benchmark](../benchmarks/compression.md) gates it: every output it
replaces has to keep the lines pre-registered as the ones a reader needs. With
the variable unset, the hooks behave exactly as before: they inject nothing.

## Opt-in: noisy install logs, trimmed (`NEURALMIND_BASH_REPLACE=1`)

The earlier hooks returned compressed text as `additionalContext`, which Claude
Code adds next to the tool result, so they cost tokens. This one returns
`updatedToolOutput`, which Claude Code uses *instead of* the result. Because a
replacement can hide what an agent needs, it is narrow on purpose:

- **An allowlist of commands, not a size threshold:** `pip install` (also
  `python -m pip install`) and `neuralmind build`, run on their own. `cd`,
  `source .venv/bin/activate` or variable assignments may come first. A pipe, a
  redirect, `||`, a subshell or a second command (`pip install -e . && pytest`,
  and anything after the install, even another `pip install`) leaves the
  output whole, and so does every other command.
- **Removes known noise, keeps everything else:** only lines matching that
  tool's progress patterns go (pip's `Collecting`, `Downloading`, progress
  bars, build steps, and `Requirement already satisfied` for a dependency).
  Every other line reaches Claude as printed, and a line mentioning an error,
  warning, failure or deprecation is never removed.
- **The rest is one Read away:** the full output, credentials redacted, is kept in its
  own file under `.neuralmind/bash_outputs/` (newest 20), and the replaced
  result ends with that file's path. A later or parallel Bash call can't
  overwrite it, unlike the single `neuralmind last` slot, which works as before.
  If the file can't be written, nothing is replaced.
- **Leaves Claude Code's own handling alone:** results Claude Code already moved
  to a file (over about 30,000 characters), interrupted, backgrounded or image
  results, and results trimming wouldn't shrink pass through untouched. The
  replacement copies the Bash result and swaps only `stdout` and `stderr`, so it
  keeps the tool's output shape. A failed command fires `PostToolUseFailure`,
  which no hook can shrink, so a failure reaches Claude exactly as Claude Code
  delivers it.

## What Claude sees

A fresh `pip install -r requirements.txt` reaches Claude as 77 lines, mostly
`Collecting …`, `Downloading …` and progress bars. With the opt-in it is:

```text
[neuralmind: 74 progress lines elided: Collecting ×24, Downloading ×48, progress bar ×2]
Installing collected packages: urllib3, typing-extensions, pygments, …
Successfully installed Jinja2-3.1.6 MarkupSafe-3.0.4 … requests-2.32.3 rich-13.9.4 …
[neuralmind: pip install progress lines elided where marked; every other line is verbatim. Full output: /path/to/project/.neuralmind/bash_outputs/33026abbedf96248.txt]
```

## Measured

On the [compression benchmark](../benchmarks/compression.md), which drives the
real hook with Claude Code-shaped payloads over a committed corpus of real
command outputs:

| Bash calls | Calls | Replaced | Tokens, no hook | Tokens, opt-in | Change |
|---|---:|---:|---:|---:|---:|
| Noisy logs (installs, builds) | 5 | 4 | 8,253 | 1,490 | −81.9% |
| Content (tests, diagnostics, diffs, listings, files, searches) | 14 | 0 | 31,473 | 31,473 | +0.0% |

- **Per noisy-log call:** mean −54.8%, from −96.5% (`pip install -e ".[dev]"`
  with its dependencies present) to 0% (`next build`, which isn't on the
  allowlist).
- **What survives:** every pre-registered must-keep line of the four replaced
  calls reaches Claude. Read and Grep results are never replaced.
- **Gated in CI:** `tests/test_compression_benchmark.py` recomputes the Bash
  calls on every run. It fails if a replaced call keeps under 95% of its
  must-keep lines, if any content output, Read or Grep result is replaced, if
  any call costs more tokens than with no hook, or if a hook response isn't
  valid JSON.
- **Checked in Claude Code 2.1.287:** in a headless session, with the variable
  set only in the project's `.claude/settings.json`, the model received the
  trimmed result. Asked about an elided line, it read the kept file. These were
  single runs, a mechanism check rather than a measurement.
- **Limits:** five commands from two tools is a small corpus. When a task
  does need an elided line, the follow-up read costs more than the original
  output did, and the benchmark measures calls, not sessions.

## Turning it on

Hooks inherit Claude Code's environment. Set the variable in
`.claude/settings.json`, or in your shell before launching `claude`:

```json
{
  "env": { "NEURALMIND_BASH_REPLACE": "1" }
}
```

No reinstall is needed: the registered `compress-bash` hook reads the variable
on every call. `NEURALMIND_BYPASS=1` still switches off every hook action,
this one included.

## What the agent actually sees after upgrading

| Agent | Variable unset (default) | `NEURALMIND_BASH_REPLACE=1` |
|---|---|---|
| Claude Code | The tool result alone, as before | `pip install` and `neuralmind build` results without their progress lines, ending with the path of the full output; every other result unchanged |
| Cursor, Cline, Continue, Codex, any MCP client | Unaffected: these are Claude Code hooks | Unaffected |

## Also

- **Reading a kept output isn't a step between files.** The Read hook records
  which file the agent read after which, for the synapse layer. A Read of a
  file under `.neuralmind/`, such as a full output this opt-in kept, is
  NeuralMind's own state, not the codebase, so it's no longer recorded. (The
  hook reading Claude Code's nested `file.content` payload, which this work
  first fixed, shipped in v4.8.1.)

## New in the repo

- `evals/compression/run.py` measures a fourth arm, the hooks with the opt-in
  set, on every Read, Bash and Grep call, and exits non-zero if a gate fails.
- The Bash corpus gains three real `pip install` logs, and every entry now
  pre-registers whether it is a `content` output or a `noisy-log`. The install
  logs' must-keep lines were committed before the trimming code.
- The benchmark drives the hooks from a directory with a `.neuralmind/`, as
  they run in a built project. Since v4.8.1 they exit at once anywhere else,
  so the as-shipped arm had been measuring that early exit (the total, +0.0%,
  is the same either way). A new gate fails the run if the opt-in replaces
  none of the noisy logs, which the retention gate alone would have passed.
- `python -m evals.compression.capture_bash --only <ids>` captures new corpus
  entries without re-capturing the rest, so existing figures don't move.
- New `NEURALMIND_BASH_REPLACE` row in the
  [CLI reference](../wiki/CLI-Reference.md#environment-variables).

## Not changed

- The default: with the variable unset, the Read, Bash and Grep hooks inject
  nothing, and the Bash hook still caches the latest successful output for
  `neuralmind last`.
- The compressor functions (`compress_bash`, `compress_read`,
  `cap_search_results`, `offload_if_large`) stay in the Python API and are
  still measured as a hypothetical arm. The opt-in doesn't use them: it removes
  noise rather than keeping signal.

## Related

- [Compression benchmark](../benchmarks/compression.md)
- Use case: [Trim noisy install logs (opt-in)](../use-cases/claude-code.md#trim-noisy-install-logs-opt-in-v4100)
- [CLI reference: `NEURALMIND_BASH_REPLACE`](../wiki/CLI-Reference.md#environment-variables)
- Previous releases: [v4.9.2](RELEASE_NOTES_v4.9.2.md) · [v4.9.1](RELEASE_NOTES_v4.9.1.md) · [v4.9.0](RELEASE_NOTES_v4.9.0.md)
