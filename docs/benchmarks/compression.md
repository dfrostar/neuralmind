# NeuralMind — tool-output compression benchmark

**What this is:** a measurement of what `neuralmind install-hooks`' PostToolUse
hooks do to the tokens Claude actually sees for `Read`, `Bash` and `Grep`
calls in Claude Code, by default and with the opt-in replacement of noisy logs
(`NEURALMIND_BASH_REPLACE=1`). It drives the real hook with the payloads Claude
Code sends and applies the hook's response the way Claude Code's documented
hook protocol applies it. It does not stop at what the compressor functions
return in isolation. Raw per-call data:

- [`bench/compression/results.json`](../../bench/compression/results.json):
  the hooks as they are now.
- [`bench/compression/results-v4.3.4.json`](../../bench/compression/results-v4.3.4.json):
  the run on v4.3.4 that led to the fix below. v4.3.5 and v4.4.0 shipped the
  same hooks.

**Reproduce it:**

```bash
git clone https://github.com/dfrostar/neuralmind && cd neuralmind
pip install -e ".[dev]" tiktoken
python -m evals.compression.run --out bench/compression
```

The Bash inputs are committed. The Read and Grep inputs are the four
public-benchmark repos at their pinned commits, cloned on first run. Runs from
two different checkout directories, each rebuilding its indexes, agreed on
every one of the 251 calls. On the 248 calls the corpus had before its
`pip install` logs were added, a run on macOS (Apple Silicon, Python 3.11) and
CI's on Linux (x86-64, Python 3.12) agreed too, so a run on either can be
committed.

## What we found in v4.3.4

**As shipped in v4.3.4, the hooks did not reduce what Claude sees. On Bash and Grep they added to it.**

| Tool call | Calls | Hook responded | Tokens, no hook | Tokens, v4.3.4 hooks | Change |
|---|---:|---:|---:|---:|---:|
| Read (whole file) | 136 | 0 | 597,002 | 597,002 | +0.0% |
| Bash | 16 | 12 | 32,581 | 38,296 | +17.5% |
| Grep, content mode | 48 | 28 | 55,800 | 68,113 | +22.1% |
| Grep, files_with_matches (the default) | 48 | 0 | 2,062 | 2,062 | +0.0% |

Three documented facts about Claude Code's hook protocol explain the table.

1. **A PostToolUse hook's `additionalContext` is added next to the tool result.
   It does not replace it.** The hooks reference describes it as a "String added
   to Claude's context alongside the tool result". NeuralMind returned its
   compressed text in that field. So Claude received the full output *and* the
   compressed copy. When the hook compressed nothing, as with any successful
   Bash output of 3,000 characters or less, the copy was the whole output
   again: `pip list`, `next build`, a file listing and a short `pytest -q` each
   doubled (+100%). Replacing a result takes a different field,
   `updatedToolOutput`, which NeuralMind didn't use.
2. **The Read hook never found the text.** PostToolUse receives the Read tool's
   structured output, with the file under `file.content`. The hook looked for
   top-level `content`, `output` or `text` keys, found none, and exited. It
   responded on 0 of 136 reads. Given a top-level `content` key instead, it did
   respond. In our run it then printed an index-build line to stdout ahead of
   its JSON, which Claude Code would reject, because hook stdout must be only
   the JSON object.
3. **Failed commands never reach a PostToolUse hook.** A command that exits non-zero
   (other than exit 1 from `grep`, `find`, `diff` and a few others) fires
   PostToolUseFailure, not PostToolUse. NeuralMind registers only PostToolUse,
   and PostToolUseFailure can add context but can never replace the result.
   The failing test run, the lint errors, the type errors and the crash
   traceback in the corpus all reached Claude untouched. Those are the outputs
   the compressor's "errors + summary" design was built for.

On macOS, Linux and WSL, Claude Code leaves the Grep tool out of the default
tool set, and searches reach hooks as Bash calls (the `grep -rn` entry below).
Where the Grep tool was used, its hook did nothing in the default
`files_with_matches` mode. On `output_mode: "content"` results longer than 25
lines it added the first 25 lines again (+10.4% to +96.2% per call).

## What the hooks do now

**From v4.5.0 they inject nothing by default, so Claude sees exactly the tool
result: +0.0% for Read, Bash and Grep alike.** The Read, Bash and Grep hooks stay
registered. The Bash hook still caches the latest successful command's output, credentials
redacted, so `neuralmind last` can show it again without re-running the
command. None of them returns context anymore.
That removes the overhead above with no reinstall. Shrinking a tool result for
real takes `updatedToolOutput`, and the retention figures
[further down](#what-the-compressors-would-deliver-if-they-replaced-the-result)
are why that isn't a drop-in switch. The one replacement there is, opt-in, is
narrow on purpose.

## The opt-in replacement: noisy logs only

**Off by default.** With `NEURALMIND_BASH_REPLACE=1` in Claude Code's
environment (for example `"env": {"NEURALMIND_BASH_REPLACE": "1"}` in
`.claude/settings.json`), the Bash hook returns `updatedToolOutput`, which
replaces a result rather than adding to it, for one kind of output: the
progress reporting of an install or an index build.

| Bash calls | Calls | Replaced | Tokens, no hook | Tokens, opt-in | Change |
|---|---:|---:|---:|---:|---:|
| Noisy logs (installs, builds, index runs) | 5 | 4 | 8,253 | 1,490 | -81.9% |
| Content (test runs, diagnostics, diffs, listings, file dumps, searches) | 14 | 0 | 31,473 | 31,473 | +0.0% |

Per noisy-log call the change averages -54.8%, from -96.5% to +0.0%:

| Command | Tokens, no hook | Tokens, opt-in | Must-keep lines reaching Claude |
|---|---:|---:|---:|
| `pip install -e ".[dev]"`, dependencies already present | 4,720 | 164 (-96.5%) | 3 of 3 |
| `pip install -r requirements.txt`, fresh environment | 2,225 | 351 (-84.2%) | 1 of 1 |
| `neuralmind build src/requests --force` | 461 | 202 (-56.2%) | 2 of 2 |
| `pip install pytest`, already installed | 200 | 126 (-37.0%) | 1 of 1 |
| `npm run build` (Next.js) | 647 | 647 (+0.0%), not replaced | — |

`next build` isn't on the allowlist: `npm run build` can run anything, and the
page-generation progress lines in Next.js's log are among its pre-registered
must-keep lines. Read and Grep results are never replaced: +0.0% on all 232 of
them.

How it decides what to replace:

- **Chosen by command; size never makes an output eligible.** The allowlist is
  `pip install` (also `python -m pip install`) and `neuralmind build`, and the
  whole command line has to be that invocation. `cd`, `source` and variable assignments may come
  first. A pipe, a redirect, `||`, a subshell or a second command
  (`pip install -e . && pytest`) leaves the output whole.
- **It removes known noise; it doesn't keep known signal.** Only lines that
  match that tool's progress patterns go: pip's `Collecting`, `Downloading`,
  progress bars, build steps, and `Requirement already satisfied` for a
  dependency (the line for a requirement you asked for stays). Each run of them
  becomes one marker, such as
  `[neuralmind: 74 progress lines elided: Collecting ×24, Downloading ×48, progress bar ×2]`.
  Every other line reaches Claude as printed. A line that mentions an error,
  warning, failure or deprecation is never removed, whatever it matches.
- **It keeps the full output.** The output, credentials redacted, goes to a
  file of its own under `.neuralmind/bash_outputs/`, and the replaced result
  ends with that file's absolute path. A later Bash call can't overwrite it the
  way it overwrites the single `neuralmind last` slot. If the file can't be
  written, or `NEURALMIND_OUTPUT_CACHE=0`, nothing is replaced.
- **It leaves Claude Code's own handling alone.** A result Claude Code moves to
  a file (a valid one over about 30,000 characters), an interrupted,
  backgrounded or image result, and a result trimming wouldn't shrink all pass
  through untouched. The replacement copies the Bash result and swaps only
  `stdout` and `stderr`, since Claude Code ignores a replacement that doesn't
  match the tool's output shape. A failed command fires `PostToolUseFailure`,
  which can't replace anything, so NeuralMind never touches a failure.

**Gates.** The benchmark exits non-zero if any of these fails, and
[`tests/test_compression_benchmark.py`](../../tests/test_compression_benchmark.py)
checks them on every CI run, recomputing the Bash calls from the committed
corpus:

- every replaced call keeps at least 95% of its pre-registered must-keep lines,
  and has some to check;
- no `content` command, Read or Grep result is replaced;
- no call costs more tokens with the opt-in than with no hook;
- every hook response is valid JSON.

**Checked in Claude Code itself.** In a headless Claude Code 2.1.287 session,
with the hook registered and the variable set only in the project's
`.claude/settings.json`, the model received the trimmed `pip install` result,
5 lines instead of 77, and answered which version of `requests` was installed
from it. Asked instead how many lines started with `Collecting`, it opened the
kept full output and counted them. Those were single runs, a check of the
mechanism rather than a measurement.

What the opt-in figures don't show:

- **A small corpus.** Five noisy-log commands from two tools. The reduction
  describes those outputs, not build logs in general.
- **Follow-up reads.** When a task does need an elided line, Claude reads the
  kept file, which costs more than the original output did. Each call is
  measured on its own, not a whole session.
- **Path length.** The replaced result names its file by absolute path,
  counted here as `/home/dev/project/.neuralmind/bash_outputs/…`. A longer
  project path costs a few more tokens per replaced call.

## What the compressors would deliver if they replaced the result

This part is **hypothetical**: it measures the compressors' own output, as a
hook returning `updatedToolOutput` would deliver it, next to what survives.

| Tool call | Calls a replacing hook could reach | Tokens, no hook | Tokens, compressor output | Change | What survives |
|---|---:|---:|---:|---:|---|
| Read (whole file) | 136 (110 compressed) | 597,002 | 79,008 | -86.8% | 93% of definitions named, **0% of source lines** |
| Bash | 15 of 19 | 32,003 | 9,093 | -71.6% | 60% of must-keep lines |
| Grep, content mode | 48 | 55,800 | 16,610 | -70.2% | 63% of matches |

The reductions are large, and so is what they cost:

- **A Read replaced by its skeleton would leave Claude unable to edit the
  file.** The skeleton names 93% of the functions and classes, but none of the
  source lines survive: it lists names, line numbers, docstring summaries and
  a call graph, not code. Claude reads a file to see the code it is about to
  change. Files under 1,500 characters stay whole, which is why 26 of the 136
  aren't compressed. Excluding the three files over 25,000 tokens, which Claude
  Code may page, the reduction is -84.7%.
- **Bash output that carries content is cut to almost nothing.** Of the lines
  a reader needs, compression keeps 0% of a `git diff`'s changed lines, 6% of
  `grep -rn` hits, 7% of a test collection and 13% of the definitions in a
  `cat`'d file. Verbose `pytest -v` output barely shrinks (-1.6%): every
  `PASSED` line matches the summary pattern.
- **On the pip install logs it is about as small as the opt-in trimming,** but
  it gets there by keeping each stream's last three lines: on the editable install it
  keeps 2 of the 3 must-keep lines, dropping `Successfully built neuralmind`,
  where the trimming keeps all three.
- **On the failures no hook can reach,** compression would keep 9 of 20 of a
  failing pytest run's must-keep lines (45%). It drops the `E` lines that
  explain each failure, such as pytest's `where 10250 = total_value_cents()`
  introspection and the list and dict diffs, because they don't match its
  error pattern. And it would turn 69 KB of mypy errors, which Claude Code
  trims to a 10,000-character excerpt, into 17,394 tokens, because every mypy
  line contains "error".

The -71.6% Bash figure is over the 15 calls a replacing hook could reach. "Must-keep" lines are pre-registered per
output type in [`evals/compression/capture_bash.py`](../../evals/compression/capture_bash.py):
the assertion lines of a failing test, a linter's diagnostics, a diff's changed
lines, every hit of a search, an install's outcome lines. They are not tuned to
the compressor, and the install-log lines were committed before the code that
trims those logs.

## Method

Every sample is one tool call, measured four ways:

- **No hook:** the tool result as Claude Code delivers it.
  - Read returns the whole file as line-number-prefixed text.
  - A valid Bash result is inline up to ~30,000 characters, then a file path
    plus a 2,000-character preview.
  - A failed one is `Exit code N` plus the output, inline up to ~10,000
    characters, then a head-and-tail excerpt.
  - Grep's content mode returns `path:line:text` lines, up to 250; its default
    mode lists files.
- **Hooks as shipped:** the payload goes through the real hook entry point
  (`neuralmind.hooks.run_hook`), and its JSON response is applied per the
  protocol.
  - `updatedToolOutput` replaces the result, if its shape matches.
  - `additionalContext` is added, with values over 10,000 characters becoming a
    path plus a 2,000-character preview.
  - Stdout that isn't valid JSON has no effect.
- **Opt-in:** the same, with `NEURALMIND_BASH_REPLACE=1` set for the hook, on
  every call, so it shows what the opt-in leaves alone as well as what it
  replaces.
  - Must-keep lines are counted in what reaches Claude after the response is
    applied.
  - A replaced result names its kept output file by absolute path under the
    hook's working directory. The benchmark shows that directory as
    `/home/dev/project`, so the counts don't depend on where it runs.
- **Compressor only:** the compressor's output in place of the result,
  rendered as Claude Code renders that tool's result.
  - `compress_read` gets the file's text, as a hook receives it in
    `file.content`, and its skeleton is counted with Read's line numbers.
  - A skeleton names its file by absolute path. The benchmark shows the
    checkout directory as `/work`, so the counts don't depend on where the
    repos are cloned.
  - What survives is counted in whole lines, with multiplicity: a line that
    appears ten times in the source counts as kept ten times only if the
    delivered text has it ten times.

Sources:

- **Protocol:** Claude Code's [hooks reference](https://code.claude.com/docs/en/hooks)
  and [tools reference](https://code.claude.com/docs/en/tools-reference), read
  2026-09-28. Re-read 2026-10-03 for the opt-in: `updatedToolOutput` "works
  for all tools", and for a built-in tool a value that doesn't match its output
  schema is ignored.
- **Payload shapes:** the Agent SDK's `sdk-tools.d.ts`
  (`@anthropic-ai/claude-agent-sdk` 0.3.283, Claude Code 2.1.283). The Bash
  output fields the opt-in checks before replacing (`interrupted`,
  `persistedOutputPath`, `backgroundTaskId` and the rest) were re-read in
  0.3.288.
- **Tokens:** tiktoken `o200k_base`, the public benchmark's tokenizer.

Inputs:

- **Read:** every `.py` file in `requests`, `click`, `flask` and `rich` at the
  public benchmark's pinned commits, with a NeuralMind index built for each
  repo so the skeletons are real.
- **Grep:** each repo's public-benchmark oracle symbols, plus four broad
  patterns (imports, `raise`, `def __init__`, attribute assignment). Each
  pattern runs in both modes.
- **Bash:** 19 real commands captured once and committed under
  [`evals/compression/corpus/bash/`](../../evals/compression/corpus/bash/):
  - test runs, passing, failing and collecting
  - `ruff`, `mypy --strict` and a crash traceback
  - `pip list`, a Next.js build and a NeuralMind index build
  - `git log --stat` and `git diff`
  - `grep -rn`, `find`, `cat` and `ls -la`
  - three `pip install` logs: a fresh install from a requirements file, an
    editable install with its dependencies present, and an install of a
    package that's already there (added 2026-10-03, captured on macOS with
    pip 26.2.1 and 24.0; the rest on 2026-09-28)

  Each command's kind is pre-registered with its must-keep lines: 5 noisy logs
  (the installs and the two builds) and 14 content outputs.

What this does not capture, and which way each gap leans:

- **The system-reminder wrapper** Claude Code puts around `additionalContext`
  isn't counted, so the as-shipped cost is slightly understated.
- **Exact rendering:** the Bash result's stdout/stderr interleaving and Claude
  Code's exact overflow wording are approximated. Both arms share the same
  rendering, so the comparison holds.
- **Read's page limit:** Read pages very large files at a token limit
  (`CLAUDE_CODE_FILE_READ_MAX_OUTPUT_TOKENS`) whose default the docs don't
  state. Whole-file reads are measured, and the Read figure is also given
  without the three files over 25,000 tokens.
- **Answer quality:** this measures tokens and what survives, not whether
  Claude answers better. With the hooks as shipped nothing is removed, so the
  question doesn't arise. The opt-in removes only progress lines, and its gate
  counts must-keep lines: a proxy for what Claude needs, not a measurement of
  its answers.

CI fails when `results.json` stops describing the code, in two places:

- [`tests/test_compression_benchmark.py`](../../tests/test_compression_benchmark.py)
  runs offline on every CI run. It recomputes the Bash results from the
  committed corpus and fails if the hooks stop doing what `results.json`
  records, or if the opt-in replacement fails one of its gates. It also pins
  the compressor thresholds and the Read hook's handling of Claude Code's
  payload, and fails if this page stops quoting its figures.
- The `public-benchmark-drift` job in
  [`bench-public-drift.yml`](../../.github/workflows/bench-public-drift.yml)
  recomputes Read and Grep too. On every pull request and push to `main`, it
  re-runs the whole benchmark over the public benchmark's pinned checkouts,
  with an index built for each repo, the opt-in arm included; the run itself
  exits non-zero if an opt-in gate fails. Every call has to match `results.json`
  exactly: the digests of what each arm delivers, the token counts and what
  survives. Only the run date and the NeuralMind version aren't compared
  ([`evals/compression/drift.py`](../../evals/compression/drift.py)). So a
  change to the skeletons, the compressors, the hooks or the index build that
  moves a published figure fails CI until someone re-runs
  `python -m evals.compression.run --out bench/compression` and commits the
  result. After a change to the index build, delete `.bench-work` first: a
  re-run updates the indexes it finds there incrementally, which keeps parts
  of the old graph. The job uploads its fresh run as the
  `compression-benchmark-drift` artifact.
