# NeuralMind v4.23.0 — the per-prompt block lists the code before its tests

**Type:** Minor release | **Theme:** the block the prompt hook adds puts test
files after the code they test, as it was meant to, unless the prompt names a
test; and a test file that matches a prompt brings the code it tests with it

Since v4.11.0, the block NeuralMind adds to each prompt (Claude Code's
`UserPromptSubmit` hook, the Hermes plugin's `pre_llm_call`) has meant to list
test files after the code they test, unless the prompt is about tests. But its
test for "about tests" was any mention of one: *test*, *tests*, *testing*,
*spec*, *pytest*. A bug report almost always has one ("the tests fail", "a
flaky test", "here's a test that reproduces it"), and every prompt in the
task-outcome benchmark does, because the harness adds a line about the
project's tests. So in practice the ordering never applied.

On the 5 tasks of a [hermes-agent](https://github.com/NousResearch/hermes-agent)
screen, 18 of the 32 files the block listed were tests. On 12 held-out tasks
from the same repository, it was 33 of 82.

---

## What changed

### A prompt is about tests when it names one

Test files now come after the code unless the prompt names a test: a
`test_*` function, a `Test*` class, or a test file's path (`tests/test_cli.py`,
`parser.test.ts`). Mentioning tests isn't enough.

| Prompt | Tests listed |
|---|---|
| "the parser drops quoted options; the tests fail" | after the code |
| "a pruning test is flaky after the refactor" | after the code |
| "why does `test_parse_quoted` fail?" | where they rank |
| "fix `tests/test_cli.py` on Windows" | where they rank |

### A matched test file brings the code it tests

A symptom often matches the test of the module to fix better than the module
itself, because the test spells out the behaviour in the prompt's own words.
On hermes-agent, a prompt about an NVIDIA error matched
`tests/agent/test_error_classifier.py` and never `agent/error_classifier.py`,
the file the fix changed. Now a matched test file credits the code file it
tests with its best score, so that file is listed even when only its test
matched.

- **Found by name only:** `test_x.py` and `x_test.py` test `x.py`,
  `x.test.ts` and `x.spec.ts` test `x.ts`, and `ParserTest.java` tests
  `Parser.java`. When several files
  share the name, the one at the test's own path with the test folders taken
  out (`tests/agent/test_x.py` → `agent/x.py`) wins. If none of them is there
  and there is more than one, nothing is credited.
- **Not when the prompt names a test.** Then the tests rank where they score.
- **`TESTED_CODE_CREDIT`** (`neuralmind/prompt_recall.py`, default 1.0) sets
  the share of the test's score the code gets. At 0 the credit is off.

### The code excerpt skips a leading test

The block quotes code when one file clearly leads (v4.21.0). The lead is now
the first non-test file, compared against every other listed file, tests
included. So a test that matches as well as its code holds the quote back
rather than being quoted.

---

## Measured: offline replays, no agent runs

These are replays of the hook's block, scored against each task's real fix by
`evals/task_outcome/replay.py`. **No agent ran.** Whether an agent does
anything differently with the new block is not measured, and none of this is a
claim on the site.

The ranking was tuned on the hermes-agent screen's 5 tasks. The choice was
fixed before the held-out results came in. The 12 held-out tasks came from
continuing the screen's seeded walk, with prompts written by a separate agent.
Both versions ran on the same index for each task, so they differ only in
ranking. Everything is in
[`bench/task_outcome/hermes-agent-test-ranking/`](https://github.com/dfrostar/neuralmind/blob/main/bench/task_outcome/hermes-agent-test-ranking/README.md).

| hermes-agent, held out (12 tasks) | v4.22.1 | v4.23.0 |
|---|---|---|
| A file the fix changed is listed | 4 | 4 |
| …and listed first | 1 | 3 |
| Code quoted / from a changed file | 2 / 0 | 2 / 1 |
| Test files among the files listed | 33 of 82 | 6 of 84 |
| Median block size (characters) | 923 | 728 |

| hermes-agent, tuned on (5 tasks) | v4.22.1 | v4.23.0 |
|---|---|---|
| A file the fix changed is listed | 2 | 3 |
| …and listed first | 1 | 3 |
| Test files among the files listed | 18 of 32 | 2 of 35 |

What the held-out numbers do and don't show:

- **Tests move to the back.** The file to fix moved to the top on 2 tasks, and
  on a third the block now quotes it.
- **The file to fix is named no more often.** It's listed on 4 of 12 either
  way. Where it was missing, other code matched the prompt, not tests sitting
  in its place.
- **Nearly all of the held-out gain comes from the narrower test rule.** The
  credit changed 2 of 84 listed files and no score there. Its gain on the
  tuning set (one task) didn't carry over.
- **12 tasks from one repository** is enough to see the order change, not to
  estimate how much it helps.

On NeuralMind's own repository, the pilot's 20-task replay (the
**Prompt-recall replay** CI gate) still passes its floors:

| Pilot, 20 tasks | v4.22.1 | v4.23.0 | Floor |
|---|---|---|---|
| A file the fix changed is listed | 17 | 17 | 15 |
| …and listed first | 10 | 11 | 9 |
| Code from a changed file / quoted | 7 of 9 | 7 of 8 | 70% |

Both ran on the same 20 indexes, built once with v4.22.1, and a second
v4.22.1 run on them matched the first exactly. The pilot's prompts end with
the same line about tests, so the old rule never moved tests back there
either.

### Tests

`tests/test_prompt_recall.py`:

- A prompt is about tests only when it names a `test_*` function, a `Test*`
  class or a test file, and a prompt that only mentions tests still lists the
  code first.
- A matched test file names the code it tests, for each naming convention
  above. The tested code keeps its own matches, and the credit can be turned
  off. A prompt naming a test credits nothing.
- The excerpt skips a leading test file, is held back by a test that matches
  as well as the code, and quotes a test file when the prompt names a test.

---

## What the agent actually sees post-install

| Agent | Before v4.23.0 | From v4.23.0 |
|---|---|---|
| **Claude Code** | On a bug report, the per-prompt block often opens with test files, because nearly every bug report mentions tests | The code first, then its tests; a matched test's code is listed even when only the test matched; tests rank first only when the prompt names one |
| **Hermes-Agent plugin** | The same block on each turn (`pre_llm_call`) | The same change |
| **Cursor / Cline / Continue / generic MCP** | No change: they don't run the prompt hook | No change. MCP `neuralmind_search` and `neuralmind_query` rank as before |

## Upgrading

Nothing to rebuild or configure: the ranking reads the index you have. If you
want tests first, name the test in the prompt.

## Use cases

- **Existing: [NeuralMind in Claude Code](../use-cases/claude-code.md).** On a
  bug report, the block now puts the code to read before the tests that
  describe it.
- **Existing: [check what your agent is handed](../use-cases/check-what-your-agent-is-handed.md).**
  This change was measured that way: tuned on one set of tasks, then replayed
  on held-out tasks from the same repository before and after, with the index
  held fixed. The held-out record shows how to do the same for a ranking change
  of your own.
