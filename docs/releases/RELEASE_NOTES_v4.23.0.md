# NeuralMind v4.23.0 — the prompt block lists the code before its tests when a prompt only says how to run them, and quotes code, not a test

**Type:** Minor release | **Theme:** the per-prompt block points at the source file to change on a repository with a large test tree

The [hermes-agent screen](https://github.com/dfrostar/neuralmind/pull/720)
ran the same agent on 5 bug fixes in
[NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent),
about a million lines of Python, with and without NeuralMind. As in the
[task-outcome pilot](../specs/TASK-OUTCOME-BENCHMARK-SPEC.md), the agent
called no NeuralMind tool in any run, so the block the `UserPromptSubmit` hook
adds to the prompt was all it got from NeuralMind. Replayed offline, that
block named a file the fix changed on 2 of the 5 tasks (17 of 20 in the
pilot, in NeuralMind's own repository). **18 of the 32 files it listed were
under `tests/`, and 2 of its 3 code excerpts quoted a test file.**

The block already ranked test files after the code they test, before cutting
the list to four files, unless the prompt was about tests. But it counted any
test word as being about tests, and the benchmark's prompt ends with how to
check the work: *"Don't add or change tests: the fix is judged by tests you
can't see. You can run the existing tests with `python -m pytest <path>`."*
So on every prompt the benchmark has run, the 20 pilot tasks and the 5 hermes
tasks alike, tests were ranked with the code, and a test file, holding many
functions that each match the prompt's vocabulary, could outscore the file to
fix and take its place.

---

## What changed

### Test words alone no longer rank the tests with the code

| The prompt | Test files in the list |
|---|---|
| names a test: a function or class (`test_parse_option`, `parse_test`, `UserServiceTest`) or a test file's path (`tests/test_parser.py`, `cart.test.ts`, `tests/`) | ranked with the code by score, as any prompt with a test word was before |
| uses a test word without naming one ("run the tests", "pytest", "fix the claims guard test") | after the code, and the best test file keeps the last of the four slots if the code would fill them |
| has no test word | after the code, as before |

"Fix the claims guard test for site numbers" is still about a test, so the
middle row keeps one test file in the list; a prompt that only tells the agent
how to run the tests gets the code first. The links in *Connected to it in the
synapse graph* follow the same order.

Queries (`neuralmind query`, MCP `neuralmind_query`) are unchanged: a
question is short, and a test word in it is about its subject, so it still
lifts the test demotion there (`NEURALMIND_TEST_FILE_FACTOR`).

### The excerpt quotes code, not a test

When one file's summed match score is at least twice the next file's, the
block quotes that file's best match (v4.21.0). Now only the listed source
files compete for it when any is listed: a test file is quoted only when no
source file is listed. On a prompt that names a test, where a test file can
come first, the excerpt line says so: *Most matches outside the tests are in
`<file>`*.

### A matched test file brings the code it tests

A symptom often matches the test of the module to fix better than the module
itself: the test spells out the behaviour in the prompt's words. On
hermes-agent, a prompt about an NVIDIA error matched
`tests/agent/test_error_classifier.py` and never `agent/error_classifier.py`,
the file the fix changed. Now, unless the prompt names a test, a matched test
file credits the code file it tests with its best score, so that file is
listed even when only its test matched.

- **Found by name only:** `test_x.py` and `x_test.py` test `x.py`,
  `x.test.ts` and `x.spec.ts` test `x.ts`, and `ParserTest.java` tests
  `Parser.java`. When several files share the name, the one at the test's own
  path with the test folders taken out (`tests/agent/test_x.py` →
  `agent/x.py`) wins; if none is there and there are several, nothing is
  credited. All-caps stems (`HTTPTest.java`) aren't mapped.
- **A file listed only through the credit has no symbol to quote,** so it
  holds the excerpt back rather than giving it one.
- **`TESTED_CODE_CREDIT`** (`neuralmind/prompt_recall.py`, default 1.0) is the
  share of the test's score the code gets; 0 turns the credit off.

### The replay scores the new line

`evals/task_outcome/replay.py` reads *Most matches outside the tests are in*
as an excerpt too, so a block whose first file is a test still has its
excerpt scored.

---

## Measured

Each set was replayed with no agent and no API cost: the hook's block for each
task's prompt, before (v4.22.1) and after, on the same indexes, scored against
the fix (`evals/task_outcome/replay.py`; see
[Check what your agent is handed](../use-cases/check-what-your-agent-is-handed.md)).
This release doesn't measure what the agent does with the block.

**The pilot's 20 tasks, NeuralMind's own repository: the check.** The change
had to keep the fixed file named on at least 17.

| Of 20 tasks | v4.22.1 | test rule, slot, excerpt only | v4.23.0 (also the credit) |
|---|---|---|---|
| The block names a file the fix changed | 17 | 17 | 17 |
| …and names it first | 10 | 10 | 11 |
| The block quotes code | 9 | 9 | 8 |
| …from a file the fix changed | 7 of 9 | 7 of 9 | 7 of 8 |
| …covering lines the fix changed | 2 of 9 | 2 of 9 | 2 of 8 |
| Test files among the files listed | 7 of 121 | 6 of 123 | 7 of 123 |
| Excerpts that quote a test file | 0 | 0 | 0 |

Without the credit, three of the 20 blocks changed, none in what they score. Test files were 7 of
the 121 files these blocks listed before the change, so here the pilot checks
for a regression; it can't show the fix working.

**The hermes-agent screen's 5 tasks: the tasks that motivated the change.**
They show what changed in the block; they can't also be evidence that the
change works, which needs tasks it wasn't made for. The v4.22.1 column
reproduces the screen's own replay (`replay-results.json` in
[#720](https://github.com/dfrostar/neuralmind/pull/720)) file for file, on the
indexes the screen's runs used (built by v4.21.0).

| Of 5 tasks | v4.22.1 | v4.23.0 |
|---|---|---|
| The block names a file the fix changed | 2 | 2 |
| …and names it first | 1 | 2 |
| The block quotes code | 3 | 1 |
| …from a file the fix changed | 1 of 3 | 1 of 1 |
| …covering lines the fix changed | 1 of 3 | 1 of 1 |
| Test files among the files listed | 18 of 32 (56%) | 6 of 35 (17%) |
| Excerpts that quote a test file | 2 | 0 |

On the other 3 tasks the fixed file isn't among the prompt's nearest index
nodes: it ranks 138th on one, and outside the first 200 on two. The hook reads
16, so no ordering of them could name it; that's a retrieval miss, not
crowding. On the task whose block now names both changed files, one of them
first, it used to list a test file first.

**12 held-out hermes-agent tasks: the new tasks.** These are bug fixes neither
change was made for: 3 screen candidates the screen didn't select, and 9 from
continuing the screen's seeded walk to its 24th candidate, with prompts written
by a separate agent from each fix's tests and diff, and 3 tasks excluded
because their tests check names the fix introduces. Each task's index was
built once (v4.22.1) and every version ran on a fresh copy of it
([held-out record](https://github.com/dfrostar/neuralmind/blob/main/bench/task_outcome/hermes-agent-test-ranking/README.md)).

| Of 12 held-out tasks | v4.22.1 | test rule, slot, excerpt only | v4.23.0 (also the credit) |
|---|---|---|---|
| The block names a file the fix changed | 4 | 4 | 4 |
| …and names it first | 1 | 3 | 3 |
| The block quotes code | 2 | 4 | 3 |
| …from a file the fix changed | 0 of 2 | 1 of 4 | 1 of 3 |
| Test files among the files listed | 33 of 82 (40%) | 16 of 83 (19%) | 14 of 84 (17%) |

- **What the screen showed holds on new tasks:** tests move behind the code,
  and the fixed file comes first on 3 tasks instead of 1.
- **The file to fix is named no more often.** Where it was missing, other code
  matched the prompt, not tests sitting in its place.
- **The credit adds little here.** It changed 3 of the 12 blocks, named no
  new changed file, and on one task its listed file left no file 2:1 ahead, so
  an excerpt from the wrong file is no longer shown. On the screen's 5 tasks,
  which it was tuned on, it named the fixed file on one more (3 of 5, first on
  3); on the pilot it put the fixed file first on one more (11 of 20) and
  quoted code on 8 tasks instead of 9, 7 of them from a changed file.
- **12 tasks from one repository** is enough to see the order change, not to
  estimate how much it helps an agent.

**The prompt-recall benchmark (`tests/benchmark/prompt_recall.py`).** 14 Click
prompts and 15 about NeuralMind's code, two of them about tests ("how can I
test a click command and capture its output?", "fix the claims guard test for
site numbers"): named 13 of 14 and 14 of 15, first 12 and 10, before and after.
One Click block gains an excerpt, from the expected file, because a test file
no longer counts as the runner-up. The claims-guard prompt is a miss both ways:
its test file isn't among the nearest nodes.

Reproduce: `python -m evals.task_outcome.replay --work-dir <scratch> --out <dir>`
for the pilot (the *Prompt-recall replay* CI job runs it, with its floors, on
every change to the hook's recall path); the hermes screen's
`evals/task_outcome/studies/hermes-agent-screen/hook_replay.py` in #720 for the
5 tasks, which needs their indexes (about 20 minutes each to build); and
`python -m tests.benchmark.prompt_recall <built project> --prompts
tests/benchmark/prompt_recall_<set>.json` for the benchmark.

### Tests

- `tests/test_prompt_recall.py`: which prompts name a test (functions, classes,
  test paths, and the benchmark's instruction, which doesn't); four test files
  that outscore the code come after it on a prompt that only says how to run
  the tests (they filled the list before); a prompt that mentions a test keeps
  one slot for it; one that names a test ranks the tests by score; linked test
  files follow the code; a test file neither competes for the excerpt nor is
  quoted while a source file is listed, and is quoted when only tests are.
- `tests/test_prompt_recall.py`, the credit: a matched test file names the code
  it tests, for each naming convention above; the tested code keeps its own
  matches, and the credit can be turned off; a prompt naming a test credits
  nothing.
- `tests/test_task_outcome_replay.py`: an excerpt after a listed test file is
  scored.

---

## What the agent actually sees post-install

| Agent | Before v4.23.0 | From v4.23.0 |
|---|---|---|
| **Claude Code** (`UserPromptSubmit` hook) | A prompt with any test word ("run the tests") listed test files with the code; on hermes-agent, 18 of 32 files listed were tests, and the excerpt could quote a test | Test files after the code unless the prompt names a test; one slot for the best test when it mentions tests; the code a matched test file tests, listed with it; the excerpt from a source file whenever one is listed |
| **Hermes-Agent plugin** (`pre_llm_call`) | The same block | The same change: the plugin runs the installed `neuralmind _hook prompt-submit` |
| **Cursor / Cline / generic MCP** | No per-prompt block; `neuralmind_query` ranks test hits below the code unless the question mentions tests | Unchanged |

## Upgrading

Nothing to do. The block is computed per prompt from the existing index, so
no rebuild is needed; the Hermes plugin calls the installed `neuralmind`, so
upgrading the package is enough.

## Use cases

- **Existing: [NeuralMind in Claude Code](../use-cases/claude-code.md).** On a
  repository whose tests repeat the code's vocabulary, the per-prompt block
  names the source files first even when the prompt says how to run the tests.
- **Existing: [Check what your agent is handed](../use-cases/check-what-your-agent-is-handed.md).**
  The share of test files among the files a block lists is worth reading
  before any score: it is how the hermes-agent replay found this.
- **New: point the block at the code, then measure it on a large test tree.**
  The hermes-agent screen's tasks can't judge this change; a study on new tasks
  in a repository with a large test tree can.
  The [held-out record](https://github.com/dfrostar/neuralmind/blob/main/bench/task_outcome/hermes-agent-test-ranking/README.md) is that study's
  offline half: 12 new hermes-agent tasks, replayed before and after on the
  same indexes, with the tasks, prompts, exclusions and script committed.
