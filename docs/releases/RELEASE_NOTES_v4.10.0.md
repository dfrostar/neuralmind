# NeuralMind v4.10.0 — Hermes can install the NeuralMind plugin itself, and the plugin says why when it can't work

**Type:** Minor release | **Theme:** Hermes-Agent plugin, ready for Hermes's own installer; and, for Claude Code, an opt-in that trims noisy install logs

v4.9.0 gave Hermes-Agent [NeuralMind's context in every turn](RELEASE_NOTES_v4.9.0.md)
through a plugin, installed with `neuralmind install-hermes-plugin`. Three things
stood between that plugin and a Hermes user finding and installing it the
Hermes way:

- **Only NeuralMind's command could install it.** Its manifest was generated
  at install, so a clone of its directory wasn't a plugin Hermes could load.
- **It went quiet when it couldn't work.** Without a NeuralMind it could run,
  or with one too old to give the recap, turns simply got no context, or no
  recap, and nothing said why.
- **Uninstalling, then installing again, left it off.** `--uninstall`
  disabled the plugin before removing it, which left it on Hermes's
  `plugins.disabled` list, and the next install respected that.

v4.10.0 fixes all three. It also adds an opt-in for Claude Code that trims the
progress lines of `pip install` and `neuralmind build` output, with the full
output one Read away: [noisy install logs, trimmed](#what-claude-sees).

## Hermes can install it

The plugin's directory, `neuralmind/hermes_plugin/`, now carries its own
`plugin.yaml` and a [README](https://github.com/dfrostar/neuralmind/blob/main/neuralmind/hermes_plugin/README.md),
so Hermes's own installer can install it from a clone of this repository:

```bash
pip install -U neuralmind                       # the plugin runs NeuralMind; it doesn't bundle it
neuralmind build /path/to/project
hermes plugins install dfrostar/neuralmind#neuralmind/hermes_plugin --enable
```

- **Hermes owns the code.** `hermes plugins update neuralmind` updates it.
- **It runs the `neuralmind` command on Hermes's PATH.** It looks only in
  absolute PATH entries, never the working directory, so a repository you work
  in can't supply its own `neuralmind`. Where Hermes's PATH doesn't include it
  (a gateway run as a service, Hermes Desktop), also run
  `neuralmind install-hermes-plugin`: on a plugin Hermes installed, it writes
  only the interpreter and the project to the plugin's `config.json`, and
  leaves the code alone. If Hermes's install records
  (`plugins/.install-metadata.json`) can't be read, it leaves the code alone
  too, and says so.
- **The manifest declares `requires_hermes: ">=0.21.5"`**, the version it's
  tested with, so an older Hermes skips it.
- **The README lists what the plugin does on your machine**: the subprocess it
  runs, what it reads and writes in the project's `.neuralmind/`, what it
  copies into Claude Code's memory directory, its network use, and what
  reaches your model provider.
- **Hermes's catalog check passes.** `hermes plugins validate` on the
  directory passes every check, the install security scan included.

`neuralmind install-hermes-plugin` works as before and stays the simplest way
in: it copies the plugin, records the Python interpreter that has NeuralMind,
and enables it.

## It says why when it can't work

When the plugin can't start NeuralMind, finds one older than 4.9, or a call
times out, it logs one warning per Hermes process, naming the fix:

```bash
hermes logs --level WARNING | grep -i neuralmind
# WARNING hermes_plugins.neuralmind: NeuralMind plugin: /home/you/.local/bin/neuralmind is
#   NeuralMind 4.3.5, too old for this plugin: turns get no session recap. Install NeuralMind
#   4.9 or later so the `neuralmind` command is on Hermes's PATH, or run
#   `neuralmind install-hermes-plugin` to point the plugin at it.
```

An older NeuralMind still answers, so before this the only sign was a missing
recap. The version check runs once per Hermes process, in the background, off
the turn's path. As before, nothing breaks the turn: it goes ahead without
NeuralMind's context.

## Fixed: a reinstall after an uninstall stays on

`neuralmind install-hermes-plugin --uninstall` now runs Hermes's own
`hermes plugins remove neuralmind`, which removes the directory and every entry
naming the plugin in that home's `config.yaml`, so installing it again later
turns it back on. A fresh install also enables the plugin whatever an earlier
one left on the disabled list; only a re-run over an existing install respects
a `hermes plugins disable neuralmind` you ran. Hermes won't remove a symlinked
`plugins/neuralmind`, so for one the command still disables the plugin and
removes the link, never what it points to. If `hermes plugins remove` fails,
even after it has already deleted the directory, the command disables the
plugin instead and says Hermes's config may still name it.

The install's last line also stopped saying "Each Hermes turn now gets
NeuralMind's related files…" when the plugin wasn't enabled (left disabled,
`--no-enable`, Hermes not set up yet, or `hermes` not on PATH). It now reads
"Once it's enabled, each Hermes turn gets …" in those cases.

## Opt-in for Claude Code: noisy install logs, trimmed (`NEURALMIND_BASH_REPLACE=1`)

An opt-in mode in which a PostToolUse hook replaces tool output rather than
adding to it, for one kind of output only: the progress lines of an install or
an index build. It is off by default, and the
[compression benchmark](../benchmarks/compression.md) gates it: every output it
replaces has to keep the lines pre-registered as the ones a reader needs. With
the variable unset, the hooks behave exactly as before: they inject nothing.

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

### What Claude sees

A fresh `pip install -r requirements.txt` reaches Claude as 77 lines, mostly
`Collecting …`, `Downloading …` and progress bars. With the opt-in it is:

```text
[neuralmind: 74 progress lines elided: Collecting ×24, Downloading ×48, progress bar ×2]
Installing collected packages: urllib3, typing-extensions, pygments, …
Successfully installed Jinja2-3.1.6 MarkupSafe-3.0.4 … requests-2.32.3 rich-13.9.4 …
[neuralmind: pip install progress lines elided where marked; every other line is verbatim. Full output: /path/to/project/.neuralmind/bash_outputs/33026abbedf96248.txt]
```

### Measured

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

### Turning it on

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

### Reading a kept output isn't a step between files

The Read hook records which file the agent read after which, for the synapse
layer. A Read of a file under `.neuralmind/`, such as a full output this opt-in
kept, is NeuralMind's own state, not the codebase, so it's no longer recorded.
(The hook reading Claude Code's nested `file.content` payload, which this work
first fixed, shipped in v4.8.1.)

### New in the repo

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

### Not changed

- The default: with the variable unset, the Read, Bash and Grep hooks inject
  nothing, and the Bash hook still caches the latest successful output for
  `neuralmind last`.
- The compressor functions (`compress_bash`, `compress_read`,
  `cap_search_results`, `offload_if_large`) stay in the Python API and are
  still measured as a hypothetical arm. The opt-in doesn't use them: it removes
  noise rather than keeping signal.

## What the agent sees

On Hermes, nothing new in a turn: the same recap and recall v4.9.0 added,
appended to the user message. What changes is that more installs actually
deliver it, and when one doesn't, Hermes's log says why. Tested against Hermes v0.21.5 (a
0.21.5+5355 main-branch build) in live `hermes chat` sessions: the first-turn
recap, recall, edits made with `patch` and `write_file`, a resumed session
(recall only), a subagent (skipped), a directory that hasn't been built
(nothing), both ways of installing, and uninstalling. What the context changes
in Hermes's answers still isn't measured.

In Claude Code, nothing changes unless you set `NEURALMIND_BASH_REPLACE=1`;
then install and build logs arrive as shown in [What Claude sees](#what-claude-sees).

## Per-agent expectations

| Agent | What changes |
|---|---|
| **Hermes-Agent** | It can install the plugin itself (`hermes plugins install dfrostar/neuralmind#neuralmind/hermes_plugin`), and update it with `hermes plugins update neuralmind`. When the plugin can't run NeuralMind, finds an old one, or times out, Hermes's log says so. Uninstalling and installing again leaves it enabled. |
| **Claude Code** | Nothing by default. With `NEURALMIND_BASH_REPLACE=1`, `pip install` and `neuralmind build` results arrive without their progress lines and end with the path of the full output; every other result is unchanged. |
| **Cursor / Cline / generic MCP clients** | Nothing. |
| **Other agents with a shell** | Nothing. |

## Use cases

- **Existing:** [Hermes-Agent with code memory in every turn](../use-cases/hermes-agent.md).
  The install step gains the Hermes-native route, and the limits section says
  where to look when turns get no context.
- **Potential:** a Hermes user who manages everything through
  `hermes plugins` can now add NeuralMind the same way as any other plugin,
  and keep it updated with the rest. Listing it in Hermes's curated plugin
  catalog, so `hermes plugins install neuralmind` finds it by name, is the
  next step; it takes a pull request to Hermes pinned to this release.
- **Existing, Claude Code:** [Trim noisy install logs](../use-cases/claude-code.md#trim-noisy-install-logs-opt-in-v4100).
  With the opt-in, an install or build log reaches the agent without its
  progress lines, and the full output is one Read away.
- **Potential, Claude Code:** a setup or environment-repair session that runs many installs
  keeps more of its context window for the work. The benchmark measures single
  calls, not sessions, so what a whole session saves isn't measured.

## Settings

One new setting, `NEURALMIND_BASH_REPLACE` (unset by default): see
[Turning it on](#turning-it-on). `NEURALMIND_PROJECT` and
`NEURALMIND_HERMES_TIMEOUT` work as in v4.9.0, and a timeout is now logged.

## Upgrading

`pip install -U neuralmind`, then re-run `neuralmind install-hermes-plugin`:
the plugin it installed is a copy, and a re-run keeps an earlier pin and leaves
a plugin you disabled disabled. A plugin Hermes installed is updated with
`hermes plugins update neuralmind` instead. `NEURALMIND_BASH_REPLACE` needs no
hook reinstall: the registered `compress-bash` hook reads it on every call.

## Privacy: ONNX Runtime telemetry

NeuralMind runs its embedding model with ONNX Runtime, and ONNX Runtime has
telemetry of its own. Its official builds turn it on by default, uploading
usage events to Microsoft from Linux and macOS (version 1.30's privacy notes
say so; we haven't checked when that started). So a NeuralMind process could
send ONNX Runtime's telemetry even though NeuralMind itself sends none. From
this release, importing NeuralMind sets `ORT_DISABLE_TELEMETRY=1`, ONNX
Runtime's switch for turning that off, before the runtime starts. A test
checks that the variable is set and that `onnxruntime` isn't loaded by the
import itself. It overrides a value you set yourself. On Windows, ONNX Runtime
writes trace events to ETW instead, which are recorded only when a Windows
trace session is collecting them; the variable doesn't change that.

## Related

- Plugin README: [neuralmind/hermes_plugin/README.md](https://github.com/dfrostar/neuralmind/blob/main/neuralmind/hermes_plugin/README.md)
- Use case: [Hermes-Agent with code memory in every turn](../use-cases/hermes-agent.md)
- Integration guide: [Hermes-Agent](../wiki/Integration-Guide.md#hermes-agent)
- CLI reference: [`install-hermes-plugin`](../wiki/CLI-Reference.md#install-hermes-plugin-v490)
- [Compression benchmark](../benchmarks/compression.md)
- Use case: [Trim noisy install logs (opt-in)](../use-cases/claude-code.md#trim-noisy-install-logs-opt-in-v4100)
- [CLI reference: `NEURALMIND_BASH_REPLACE`](../wiki/CLI-Reference.md#environment-variables)
- Previous releases: [v4.9.2](RELEASE_NOTES_v4.9.2.md) · [v4.9.1](RELEASE_NOTES_v4.9.1.md) · [v4.9.0](RELEASE_NOTES_v4.9.0.md)
