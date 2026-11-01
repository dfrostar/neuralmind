# NeuralMind v4.24.0 — lexical anchoring for the per-prompt block, behind a flag, with its pre-registered replay

**Type:** Minor release | **Theme:** the exact strings a prompt quotes can name the file to fix when the embedding search can't; off by default until a confirmation replay, with the pre-registration, the replay and its misses published

On the 12 held-out [hermes-agent](https://github.com/NousResearch/hermes-agent)
bug-fix tasks of the task-outcome work, the block the `UserPromptSubmit` hook
adds to each prompt named a file the fix touched on 4 of 12, under every
ranking tried (v4.23.0's test ordering and tested-code credit included). The
file wasn't among the embedding hits at all. Yet on 6 of those 12 the prompt
quoted an exact string that lives in the file to fix: an error message, a
dict key, a constant, a function name.

This release adds that evidence to the block's ranking, behind
`NEURALMIND_RECALL_LEXICAL=1`. **With the flag unset, nothing changes:** the
block is byte-identical to v4.23.3's and no lookup runs.

## What the flag does

With it set, `recall()`:

- **extracts the prompt's exact identifiers:** each backticked span and each
  quoted span of 8 characters or more, whole and by identifier-like word;
  `--flags`; snake_case, CamelCase and UPPER_CASE names. Common words, URLs
  and spans made only of common words are dropped; at most 24 identifiers,
  in order of appearance;
- **looks each one up in the working tree** with one `git grep -l -F
  --untracked` per identifier, over the files the index holds code nodes for
  (tracked or untracked, not ignored). Test files give no lexical evidence
  unless the prompt names a test, the rule the ranking already applies to
  them; an identifier in more than 60 files is dropped as uninformative;
- **scores each file found** by the sum over its identifiers of
  1 / ln(1 + files holding the identifier): an identifier found in one file
  is worth 1.44, in two 0.91, in five 0.56; and adds half of that to the
  file's summed embedding score, through the file's own node, so a file no
  hit is in can still be listed, without a symbol;
- **leaves everything after that unchanged:** tests after the code, the
  reserved test slot, the tested-code credit, the excerpt's 2:1 margin, the
  linked section, the docs line and the hook's similarity gate.

The build's BM25 index isn't used: it holds each code node's symbol name and
path and the docstrings, not the source text, and the identifiers that find
a file are mostly string literals and constants.

## What it measured, offline

Pre-registered first, in the task-outcome spec's change log (2026-11-01):
the gate, the weight's tuning grid, and the sets. Then replayed through the
real `neuralmind _hook prompt-submit` on the same cached indexes as the
v4.23.0 study, so the flag is the only difference between the rows
(`bench/task_outcome/lexical-anchoring/`):

| | flag off | flag on | gate |
|---|---|---|---|
| Held out, 12 hermes-agent tasks: a file the fix changed is listed / listed first | 4 / 3 | **7 / 5** | ≥ 6 / ≥ 5 |
| Held out: test files among the files listed | 14 of 84 | 14 of 84 | not above |
| Pilot, 20 tasks on this repository: listed / first | 17 / 11 | **18 / 13** | ≥ 17 / ≥ 11 |
| Median hook time, hermes-agent / this repository | 9.32 s / 0.50 s | 9.82 s / 0.68 s | |

The gate held. The two new held-out firsts are one quoted string each, found
in exactly one file; one gold file went from absent to second; the three
firsts the hook already had held; five tasks stay unnamed, three of them
with no identifier in the file to fix at all. On the pilot the flag gains one
task listed and first and two firsts, and loses one first to the `cli.py`
the quoted flags live in. The hook times on hermes-agent are cold graph
loads (those indexes predate the graph cache); the flag's own cost is the
grep, about 0.1 s on this repository and 1–2 s on hermes-agent's 20,000
tracked files.

**What it doesn't show.** 12 tasks from one repository, with the first count
exactly on its threshold, and prompts written by an agent from each fix's
tests and diff, which may quote messages more faithfully than a user's
report would. Whether an agent does anything differently with the new block
is not measured. So the default stays off: the next step is confirmation on
12 new held-out tasks from the same seeded walk before any agent run, and
the flip, if it comes, with a persisted per-file token index so a large
repository doesn't pay the grep on every prompt.

## What the agent sees

| Agent | Default | With `NEURALMIND_RECALL_LEXICAL=1` |
|---|---|---|
| Claude Code (`UserPromptSubmit` hook) | Unchanged | The same block, with files the prompt's exact strings are in added to its ranking; a file named on lexical evidence alone has no symbol after it |
| Hermes Agent (plugin `pre_llm_call`) | Unchanged | Same as Claude Code; set the variable in the gateway's environment, where the hooks run |
| Cursor, Cline, generic MCP | Unchanged | Unchanged: the flag is for the prompt hook, not the MCP query path |

## Reference

- `NEURALMIND_RECALL_LEXICAL` (off): CLI reference, Environment Variables.
- `bench/task_outcome/lexical-anchoring/README.md`: the replay, task by
  task, and how to reproduce it; `replay_lexical.py` is the script.
- `docs/specs/TASK-OUTCOME-BENCHMARK-SPEC.md`, change log, 2026-11-01: the
  pre-registration and the result.
