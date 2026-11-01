# Lexical anchoring for the prompt hook's block: offline replay

**Offline replays only, no agent runs, and not a product claim.** What the
`UserPromptSubmit` hook's block lists with lexical anchoring off and on
(`NEURALMIND_RECALL_LEXICAL=1`), scored against each task's real fix, on the
12 held-out hermes-agent tasks, the pilot's 20 tasks and the hermes-agent
screen's 5. Pre-registered, with its gate, in
[the spec's change log](../../../docs/specs/TASK-OUTCOME-BENCHMARK-SPEC.md)
(2026-11-01), before any of the code here was written. Whether an agent does
anything differently with the new block is not measured.

## Why

On the held-out tasks the block named a file the fix touched on 4 of 12
(first on 3) under every ranking tried
([hermes-agent-test-ranking](../hermes-agent-test-ranking/README.md)), because
the file wasn't among the embedding hits at all. A git-grep replay of the exact
identifiers in each prompt, scoring files by the sum over matched identifiers
of 1 / ln(1 + files matching the identifier), named 6 of the 12 (first on 3),
with firsts disjoint from the hook's: 7 named and 6 first together, a bound no
fusion can beat. On the pilot's 20 it named 17 (first 11), the hook's own
figures. The question here is whether adding that evidence to the block's
ranking gets the held-out count to the gate while holding the pilot's floors.

## What the flag does

With `NEURALMIND_RECALL_LEXICAL=1`, `neuralmind.prompt_recall.recall`:

- extracts the prompt's exact identifiers: each backticked span and each
  quoted span of 8 characters or more, whole and by identifier-like word;
  `--flags`; snake_case, CamelCase and UPPER_CASE names; common words, URLs
  and spans made only of common words dropped; at most 24, in order of
  appearance;
- looks each one up in the project's working tree with `git grep -l -F`,
  over the files the index holds code nodes for, test files left out unless
  the prompt names a test, an identifier in more than 60 files dropped;
- scores each file found by the sum over its identifiers of
  1 / ln(1 + files holding the identifier), and adds `LEXICAL_WEIGHT` times
  that to the file's summed embedding score through its own file node, so a
  file no hit is in can still be listed (without a symbol);
- leaves everything after that unchanged: tests after the code, the reserved
  test slot, the tested-code credit, the excerpt's 2:1 margin, the linked
  section, the docs line, and the hook's similarity gate.

With the flag unset the block is byte-identical to before and the grep never
runs (`tests/test_prompt_recall_lexical.py`).

## Method

- **Tasks and prompts** are the test-ranking study's, unchanged:
  [heldout/tasks.json](../hermes-agent-test-ranking/heldout/tasks.json) (12
  hermes-agent tasks, prompts written by a separate agent from each fix's
  tests and diff), `evals/task_outcome/tasks.json` (the pilot's 20, this
  repository) and `evals/task_outcome/studies/hermes-agent-screen/tasks.json`
  (the screen's 5, the ranking changes' tuning set).
- **Same indexes for every row.** Each task's index was built once with
  v4.22.1 for the test-ranking study and is reused here; every hook call and
  every in-process recall runs on a fresh APFS clone of it, so the flag is
  the only difference between the flag-off and flag-on rows, and the flag-off
  rows reproduce that study's `#731 + credit` rows.
- **Weight.** `LEXICAL_WEIGHT` was chosen from the pre-registered grid
  {0.25, 0.5, 1.0} on the pilot's 20 and the screen's 5, in-process on cached
  search hits (n = 128; [variants-pilot.json](variants-pilot.json),
  [variants-dev.json](variants-dev.json)), by named then first over both
  sets, ties to 0.5, and fixed before the held-out replay, which ran once.
  The flag-off rows match the test-ranking study's hook replays exactly.

  | In-process, flag off / on at each weight | off | 0.25 | 0.5 | 1.0 |
  |---|---|---|---|---|
  | Pilot, 20: listed / first | 17 / 11 | 17 / 13 | 18 / 13 | 18 / 13 |
  | Pilot: code quoted / from a changed file | 8 / 7 | 8 / 8 | 10 / 9 | 10 / 8 |
  | Pilot: test files among the files listed | 7 of 123 | 5 of 132 | 3 of 133 | 4 of 133 |
  | Screen, 5: listed / first | 3 / 3 | 3 / 3 | 3 / 3 | 3 / 3 |
  | Screen: test files among the files listed | 6 of 35 | 6 of 35 | 6 of 35 | 8 of 35 |

  0.5 and 1.0 tie on listed and first (21 and 16 over both sets); 0.5 keeps
  it, and lists fewer test files. The replays below ran at 0.5.
- **Scored by `evals/task_outcome/replay.py`'s `score()`** on the block the
  real `neuralmind _hook prompt-submit` printed: *named*, a file the fix
  changed is listed; *first*, it's listed first; *excerpt on gold*, the
  quoted code is from such a file. Each row also records the hook's wall
  time per call and, recomputed in-process on the same workspace, the
  identifiers extracted and the files each matched (`lexical_replica`, made
  with the hook's own matcher on the task's graph, so it is the evidence the
  ranking used; an identifier past the 60-file cut is recorded by its count).
- **Hermes.** Nothing here runs hermes-agent code; `hermes --version` was
  checked before and after.

## Result

**The pre-registered gate holds, on all three conditions.** Through the real
`neuralmind _hook prompt-submit`, flag off against flag on, at
`LEXICAL_WEIGHT = 0.5`:

| Held out, 12 hermes-agent tasks | flag off | flag on | gate |
|---|---|---|---|
| A file the fix changed is listed | 4 | **7** | ≥ 6 |
| …and listed first | 3 | **5** | ≥ 5 |
| Code quoted / from a changed file | 3 / 1 | 3 / 1 | |
| Test files among the files listed | 14 of 84 | 14 of 84 | not above 14 of 84 |
| Median block size (characters) | 804 | 804 | |
| Median hook time (seconds) | 9.32 | 9.82 | |

| Pilot, 20 tasks | flag off | flag on | gate |
|---|---|---|---|
| Listed | 17 | **18** | ≥ 17 |
| First | 11 | **13** | ≥ 11 |
| Code quoted / from a changed file | 8 / 7 | 10 / 9 | |
| Test files among the files listed | 7 of 123 | 3 of 133 | |
| Median hook time (seconds) | 0.50 | 0.68 | |

| Screen, 5 tasks (tuning set) | flag off | flag on |
|---|---|---|
| Listed / first | 3 / 3 | 3 / 3 |
| Code quoted / from a changed file | 1 / 1 | 1 / 1 |
| Test files among the files listed | 6 of 35 | 6 of 35 |
| Median hook time (seconds) | 7.79 | 9.67 |

The flag-off rows are the test-ranking study's `#731 + credit` rows, task
for task ([heldout/flag-off](heldout/flag-off/replay-results.json),
[pilot/flag-off](pilot/flag-off/replay-results.json),
[dev/flag-off](dev/flag-off/replay-results.json)); the flag-on rows are
[heldout/flag-on](heldout/flag-on/replay-results.json),
[pilot/flag-on](pilot/flag-on/replay-results.json) and
[dev/flag-on](dev/flag-on/replay-results.json). Each task's record holds the
files listed, the excerpt, the hook's seconds, and under `lexical_replica`
the identifiers extracted, the files each matched and the lexical scores,
recomputed on the same workspace.

Held out, task by task (the flag changed 6 of the 12 blocks):

| Task | Gold | Off: first file | named/first | On: first file | named/first |
|---|---|---|---|---|---|
| `e9eba2188a` | hermes_cli/web_server_sessions.py | apps/desktop/electron/local-gateway.ts | - | apps/desktop/electron/local-gateway.ts | - |
| `24b4f90e97` | hermes_cli/update_custody.py | hermes_cli/update_cmd_commit.py | - | hermes_cli/update_custody.py | named/first |
| `3c53adbc1e` | tools/bot_desktop/rfb_filter.py | hermes_cli/web_routers/display.py | - | hermes_cli/web_routers/display.py | - |
| `1c39127d37` | agent/display.py | agent/memory_manager.py | - | agent/memory_manager.py | - |
| `0cb3760383` | hermes_cli/model_switch.py | hermes_cli/model_switch.py | named/first | hermes_cli/model_switch.py | named/first |
| `44cf71f231` | agent/conversation_compression.py, hermes_state_messages.py | hermes_cli/observability/shared_metrics_efficiency.py | named | hermes_cli/observability/shared_metrics_efficiency.py | named |
| `a3537b6f04` | hermes_cli/cli_modern_layout.py | hermes_cli/cli_modern_layout.py | named/first | hermes_cli/cli_modern_layout.py | named/first |
| `cd69be6909` | tui_gateway/methods_config.py | hermes_cli/cron.py | - | tui_gateway/methods_config.py | named/first |
| `4a78de2805` | tools/terminal_tool_backends.py | hermes_cli/setup_terminal.py | - | hermes_cli/setup_terminal.py | named |
| `e3fbd32d26` | hermes_cli/gateway_setting_commands.py | hermes_cli/gateway_agent.py | - | hermes_cli/gateway_agent.py | - |
| `d4fa373017` | hermes_cli/profile_distribution.py | hermes_cli/profile_distribution.py | named/first | hermes_cli/profile_distribution.py | named/first |
| `696f6e9ff9` | agent/agent_runtime_helpers.py | hermes_state_sessions.py | - | tui_gateway/methods_prompt.py | - |

What it shows, and what it doesn't:

- **The two new firsts are one quoted string each.** On `24b4f90e97` the
  prompt quotes the message "the command would start outside the update job",
  which is in one file, `hermes_cli/update_custody.py`; every other identifier
  (`hermes update`, `update`, `would`, `start`) is in hundreds of files and
  was dropped. On `cd69be6909` the quoted log line "readiness check still in
  progress; retrying next tick" is in `tui_gateway/methods_config.py` alone,
  and the dotted names `setup.status`, `setup.runtime_check` and `setup.ready`
  add to it; the file the embedding ranked first, `hermes_cli/cron.py`, drops
  out of the list. The git-grep replay that motivated this change took only
  backticked spans and so had nothing on `24b4f90e97`: the quoted-message
  rule, pre-registered, is what found it. That is also why the fused block
  names 7 where that replay's union with the hook gave 7 and its first 5
  against the union's 6: the bound was for a different extractor.
- **One gold file goes from absent to second.** On `4a78de2805`,
  `tools/terminal_tool_backends.py` holds the one-file identifier
  `_build_sandbox_env` and three of the backend names, but
  `hermes_cli/setup_terminal.py` keeps first on its embedding matches plus
  lexical evidence of its own, and keeps the excerpt (from the wrong file,
  as before).
- **The three firsts the hook already had hold** (`0cb3760383`, `a3537b6f04`,
  `d4fa373017`). On `0cb3760383` the lexical ranking alone had
  `runtime_provider.py` ahead of the gold file by 0.08; the embedding
  evidence decided it. On `d4fa373017` the lexical evidence tied the gold
  file with `profile_cmd.py`; the embedding evidence decided it too.
- **Five tasks stay unnamed.** On `e9eba2188a` the gold file's lexical score
  (`owner_unreachable` in two files, `storage_unavailable` in 23) wasn't
  enough against the electron file's embedding matches: the block is
  unchanged. On `696f6e9ff9` the identifiers (`confirm_truncate`,
  `truncate_before_row_id`, the quoted message) point to the TUI gateway and
  the desktop app's rewind code, where the protocol is handled, not to the
  `agent/` helper the fix changed: the block changed, to other wrong files.
  `3c53adbc1e`, `1c39127d37` and `e3fbd32d26` have no identifier in the gold
  file.
- **Test files don't gain.** They're left out of the lexical evidence unless
  the prompt names a test, and the count is unchanged held out (14 of 84) and
  lower on the pilot (3 of 133 against 7 of 123), where lexical code files
  push them off the list.
- **On the pilot** the flag gains one task listed and first (`1015eb8b95`:
  the prompt quotes a dozen JSON keys that are all in `neuralmind/cli.py`)
  and two firsts (`454904f4bb`, `4325e063e1`), and loses one first
  (`b06a3ee6af`: the quoted `neuralmind license renew --customer Acme --term
  12` has its flags in `cli.py`, which outranks the operations module it
  calls; the module is still second). 18 of the 20 blocks changed somewhere
  in their list. Both are the CI replay's floors with room to spare, but that
  job runs with the flag off, so it doesn't yet guard this ranking.
- **The hook is slower with the flag on.** On hermes-agent the median rose
  from 9.32 to 9.82 s held out and from 7.79 to 9.67 s on the screen's
  tasks; on this repository from 0.50 to 0.68 s. The added part is the
  grep, one `git grep -l -F` per identifier over 20,000 tracked files, 6 to
  16 identifiers a prompt. The absolute times are high because these indexes
  were built by v4.22.1, before the graph cache, so every call loaded the
  graph cold (about 6.5 s on hermes-agent; 1.3 s with the cache, per the
  v4.23.0 notes), and this Mac's swap was nearly full during the run. The
  grep's cost doesn't depend on either; a persisted per-file token index,
  written at build, would remove it.
- **The first count sits exactly on its threshold.** 5 of 12, from two tasks
  changing. The gate was set before the code was written and the replay ran
  once, but 12 tasks from one repository can't say how big the effect is,
  and the prompts were written by an agent from each fix's tests and diff,
  so they may quote messages more faithfully than a user's report would.
  The pre-registered next step is confirmation on 12 new held-out tasks
  from the seeded walk (seed 20261025, positions 25 onward) before any agent
  run; the default stays off until then.

**The rows here are from a second run of all six.** After the first run,
review changed the code (URLs blanked before every extraction pass, `git
grep --untracked`, a file-level entry for a file the graph has no file node
for) and the diagnostic record (the replica now uses the hook's own matcher
on the task's graph, so it applies the index filter). Every one of the 72
blocks came back identical to the first run's, so the counts above are the
pre-registered single replay's; the hook times are the second run's, and six
pilot records' `lexical_replica` changed because the first run's replica had
counted grep hits in files the index doesn't hold (a minified chart bundle
under `docs/benchmarks/`, the site's Tailwind config).

## Reproduce

Needs the cached indexes from the test-ranking study under `~/nm-bench`
(`heldout/index/<tid>`, `index-cache/<tid>`, `pilot-merged/<tid>`; set
`NM_BENCH` for another root), a hermes-agent clone at `~/nm-bench/hermes-agent`,
and a *shim* per row: a directory with a `neuralmind` executable that runs the
NeuralMind under test and exports `NEURALMIND_RECALL_LEXICAL` itself (the
hook's environment is cleaned of every `NEURALMIND_*` variable), for example
`PYTHONPATH=<checkout> exec python -P -m neuralmind "$@"`. The `-P` matters:
inside a NeuralMind checkout, as on the pilot's tasks, `-m` would otherwise
import the checkout's own copy of `neuralmind`.

```bash
python replay_lexical.py prepare <set>                  # set: heldout | dev | pilot
python replay_lexical.py capture <set>                  # cached search hits, for variants
python replay_lexical.py variants <set> 0.25 0.5 1.0    # the weight grid, in-process
python replay_lexical.py hook <set> <shim-off> flag-off
python replay_lexical.py hook <set> <shim-on> flag-on
python replay_lexical.py summary                        # the tables above
```

Run the heavy steps one at a time: `capture`, `variants` and `hook` load
hermes-agent-scale graphs (1.75 GB each). On one M3 a hook row took about a
minute on the pilot's 20 tasks and two on the held-out 12.
