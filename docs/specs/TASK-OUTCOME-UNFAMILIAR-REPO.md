# Task outcomes, track 2: a frontier agent on an unfamiliar large repository, against a free keyword hook

**Status:** draft, not yet pre-registered. It becomes pre-registered when it is
committed on `main` before any run; until then every section may change.
**Owner:** Darren Frost. **Machine:** a Mac with a Claude Code sign-in that is
not an employer's (the pilot's standalone login). **Harness:**
`evals/task_outcome/run.py`, as in
[`TASK-OUTCOME-BENCHMARK-SPEC.md`](TASK-OUTCOME-BENCHMARK-SPEC.md), whose
endpoints, missing-data rules and deviation-logging rules apply unchanged
except where this document says otherwise.

## Why this track

Five task-outcome studies found no significant difference in tasks solved or
cost (pilot, v4.21.0 rerun, hermes-agent screen, Hermes pilot, memory track).
An independent assessment of 4.24.0 (2026-11-03, 105 search questions on six
codebases) then found that a BM25 keyword search over file names and
docstrings put the right file in its top five as often as NeuralMind (101 of
105 each) and ranked it first a little more often (80 against 74, not
significant), and that the prompt hook named the right file on 17 of 25
prompts where that keyword search named it on 22. Its conclusion for a buyer
was: don't expect the free core to find code better than free tools, and no
agent benefit has been shown.

That is the question an enterprise evaluator will ask, and no study here has
put it to an agent: **does the prompt-time block change what a frontier
agent does on a repository it doesn't know, and does it do more than the same
block filled by a free keyword search would?** The one setting with room for
an effect is a large unfamiliar repository, where the agent's own search is
the cost NeuralMind is meant to shorten. The hermes-agent screen tested that
setting with Claude Code on 5 tasks at 4.21.0 and recommended stopping
(median cost +1.5%, 95% CI −28.1% to +5.2%, 5 solved against 4). Since then
the block's ranking changed three times (#731, the tested-code credit,
lexical anchoring), and each change was measured offline only.
[Track 1](TASK-OUTCOME-BIGREPO-SMALLMODEL.md) runs the same setting with a
local 20B model. This track runs it with the agent enterprises actually pay
for, on 20 tasks, with a third arm that the assessment makes necessary.

What a result buys:

- **Supported:** the first sentence about agents the site could quote, with
  its interval, and the one that distinguishes NeuralMind from a free tool.
- **Not supported:** the agent story ends for frontier models on this
  evidence, and the product is presented as what the retrieval numbers show:
  local code search with an auditable trail, priced for seats and support.
  That is a usable answer too, and it is published with the same prominence.

## Question

On the same real bug-fix tasks in a large repository the agent has never
seen, does the same coding agent cost less per task with NeuralMind's prompt
hook than with no hook, and less than with a free keyword hook in the same
place, without solving fewer tasks?

## Arms

Three, identical except for what the `UserPromptSubmit` hook adds to the
prompt. No arm has an MCP server: in every Claude Code study so far the agent
never called NeuralMind's tools, and the block was the channel that worked,
so the MCP server would add a difference between arms that nothing uses.

| | `baseline` | `keyword` | `neuralmind` |
|---|---|---|---|
| Agent | Claude Code headless (`claude -p`) | same | same |
| Settings loaded | project only, `--strict-mcp-config`, no MCP server | same | same |
| Prompt hook | none, `NEURALMIND_BYPASS=1` | the keyword hook below, from the project's `.claude/settings.json` | `neuralmind install-hooks`, lexical anchoring on (`NEURALMIND_RECALL_LEXICAL=1`) |
| Other NeuralMind hooks | none | none | the rest of `install-hooks` (recap, edit learning, stale-decision guard), as a user gets them |
| Index | none | the keyword index, built before the clock starts | `neuralmind build`, once per task (`--index-cache`), restored into every run |
| Tools | the allowlist in `run.BASE_TOOLS` | same | same |
| Budget cap | `--max-budget-usd 3` | same | same |
| Timeout | 1800 s | same | same |

The agent is not told about either hook. Runs are interleaved in a seeded
random order across all three arms (`--order-seed`), so no arm runs first in
bulk. Each (task, arm) pair runs 3 times.

**Why `neuralmind` runs with lexical anchoring on.** Track 1's stages 0 and
0b passed their gates with the flag on, at the threshold both times. The flag
is default-off in the release. This track measures the block at its best
offline configuration; if that configuration shows nothing with an agent,
the default-off question is settled too.

### The keyword hook

The assessment's baseline, reimplemented as a stdlib Python script in
`evals/task_outcome/keyword_hook.py`, so anyone can read exactly what the
free arm gets. It is a benchmark fixture, not a product feature, and it never
imports `neuralmind`.

- **Index.** Built once per task from the workspace, before the run: for every
  `.py` file the profile counts as source or test, one document holding the
  file's path split on `/`, `_` and case, every module-, class- and
  function-level name, and every docstring. Nothing else from the file.
  Tokens are lower-cased words of 3 characters or more; a generic English and
  programming stop list is dropped. Standard BM25 (k1 = 1.2, b = 0.75).
- **Query.** The whole prompt, tokenised the same way.
- **Block.** The top 5 files by score, as a `## Related files` list of paths
  with the matched names after each path, in the same hook output format
  NeuralMind uses (`additionalContext`), with no excerpt, no call graph and
  no learned section. Test files are listed after source files unless the
  prompt names a test, the rule NeuralMind's block applies.
- **Silence.** None: it always lists 5 files. NeuralMind's block has a
  relevance gate and a 2:1 margin gate for its excerpt; the assessment found
  the relevance gate passed every prompt it tried, so the arms differ here
  only in the excerpt.
- **Recorded per run,** as for NeuralMind's block: the files listed in order,
  whether one is a file the fix changed, whether the first is, and the block's
  SHA-256. The text stays out of git with the transcript.

The hook's accuracy on the 20 tasks, scored by `evals/task_outcome/replay.py`'s
`score()` beside NeuralMind's block flag off and flag on, is published in the
results folder **before any agent run**. That is the manipulation check for
the arm, and it is what makes a null result readable: a block that names the
right file and changes nothing is a different finding from a block that is
wrong.

## Tasks

**Repository:** NousResearch/hermes-agent, pinned at `710fa8a`, the profile
`hermes-agent` in `evals/task_outcome/profiles.py`, unchanged.

**The 20 tasks are track 1's 20,** by id, in its order: the 12 held-out tasks
of `bench/task_outcome/hermes-agent-test-ranking/heldout/tasks.json`, the
screen's 5, and track 1's three confirmation tasks (`f94d72f7e8`,
`ebf002cd3e`, `5381678d03`). If track 1's floor check replaces any task, this
track uses the replacement list as committed there. Sharing the list means
the two tracks' results can be read side by side: a frontier model and a 20B
model on the same tasks with the same block.

**What the agent sees.** The prompts are the ones already committed: the
symptom a user would report, written by a separate agent from each fix's
tests and diff, never naming the file, function or test to change, with the
suffix `run.PROMPT` that says how to run the tests and not to change them.
The agent starts from the fix's parent commit as a one-commit repository, so
it cannot read the fix or the later history.

**Disclosed.** The screen's 5 tasks were the tuning set for #731 and the
tested-code credit, and with the pilot's 20 the tuning set for lexical
anchoring's weight. The other 15 tasks have never tuned anything. Every
endpoint is reported on all 20 and on those 15 separately; the decision rule
reads all 20, as registered here.

## Endpoints

The unit of analysis is the task; each arm's 3 runs on a task are averaged.
Cost is Claude Code's reported `total_cost_usd`; a timed-out run counts as
unsolved at the budget cap, the worst case for its arm, as the main spec
says.

Two paired comparisons, each with the main spec's endpoints:

- **A: `neuralmind` against `baseline`.** Does the block help at all?
- **B: `neuralmind` against `keyword`.** Does it help more than a free hook?

For each: the one-sided exact Wilcoxon signed-rank test on per-task cost
difference; the median per-task relative cost change with a 95% bootstrap
interval (10,000 resamples, seed 20261014); and the exact McNemar test on
tasks only one arm solves, where a task is solved by an arm when most of its
3 seeds solve it. The `keyword` arm against `baseline` is reported with the
same figures, not tested for any claim.

**Mechanism, reported, not tested,** per arm: tool calls before the first
read of a file the fix changed; tool calls before the first edit; whether a
gold file was edited; turns, minutes; and the block's accuracy on each run
(named, first). This separates "the hint was wrong" from "the hint was
ignored" from "the hint was followed and it didn't matter".

## Decision rule

The sentence **"On a large repository it doesn't know, a coding agent
finishes the same tasks for less with NeuralMind, and for less than with a
free keyword hook"** is supported only when all of these hold:

1. comparison A: Wilcoxon p < 0.05 and the upper bound of the 95% interval
   on the median relative change is below zero;
2. comparison B: the same two conditions;
3. `neuralmind` solves at least as many tasks as each other arm, minus one
   (the main spec's non-inferiority margin).

Both comparisons must pass, so this is an intersection-union test and no
multiplicity adjustment is applied: it can only be harder to pass than
either test alone.

If A passes and B does not, the finding is **"NeuralMind's hook beat no hook
on this repository; its advantage over a free keyword hook was not
established"**, with B's interval beside it. B can fail because the interval
is wide as well as because the hooks are alike, and the two are not read the
same way. The stronger sentence, **"a free keyword hook gives the same
help"**, is published only on a pre-specified equivalence margin: when B's
95% bootstrap interval on the median relative cost change lies entirely
within ±5%, and the two arms' solve counts differ by at most one. Otherwise
the comparison is reported as not established, in either direction. Neither
sentence is a NeuralMind product claim.

If A does not pass, the result is reported as what it is: no difference
shown, or a loss, as for every study before it.

**Size.** 20 tasks × 3 arms × 3 seeds = 180 runs. The pilot's and the
screen's per-task relative cost changes both had a standard deviation of
about 0.13, so 20 tasks detect a median reduction of about 7.5% at 80% power
(one-sided α = 0.05, the main spec's formula). Power is not a verdict: a
non-significant result still has a 20% chance of having missed an effect of
that size. So **a null result is read by its interval, not by the power
calculation.** The practically meaningful saving is fixed here at a 10%
median cost reduction, the threshold the hermes-agent screen used to
recommend a full study. A null result is published as "a 10% saving is ruled
out on these tasks" only when the lower bound of comparison A's 95% interval
on the median relative change is above −10%; otherwise it is published as
"no difference shown, and a 10% saving is not ruled out". At the screen's
rate (about $0.21 per run, cap $3) the run costs about $40; at the cap
throughout, $540.

## Stages

| Stage | What | Gate to go on |
|---|---|---|
| 0. Prerequisites | the keyword hook and its tests; the runner gains the `keyword` arm (records `harness_version` as a new number); pins recorded; the three blocks' offline accuracy on the 20 tasks published in the results folder | the keyword hook names a gold file on at least as many of the 20 as the assessment's figure would predict (its baseline named 22 of 25 of its own prompts; here the count is reported, not gated), and NeuralMind flag-on reproduces track 1's stage 0/0b rows task for task |
| 1. Smoke | the first 2 tasks × 3 arms × 1 seed, to `bench/task_outcome/unfamiliar-repo-smoke/`, never pooled | all 6 runs recorded; every `neuralmind` run recorded NeuralMind's prompt hook, every `keyword` run its block, and no `baseline` run either |
| 2. Full run | 180 runs to `bench/task_outcome/unfamiliar-repo/` | the decision rule, applied by `analyze.py` after the analysis code for the three-arm variant is committed and before any arm comparison is read |
| 3. Replication | only if stage 2 supports the full sentence: the same design on a second repository (below), before any site claim | the same decision rule |

**Pinned before stage 1:** the model (`claude-sonnet-5-5`, as the pilot and
the screen), the Claude Code version, the NeuralMind release (the current
PyPI release when stage 0 completes; no ranking change is made between
pinning and the end of stage 2), and the test environment (Python 3.14.7 with
hermes-agent's pinned dependencies plus `pyyaml`, as the screen). Each is
written to the change log with the date.

### A second repository, for stage 3 and for the "one repository" threat

Every task-outcome study so far has run on NeuralMind's own repository or on
hermes-agent. A result that transfers needs a second large codebase. The
choice is made by rule, before stage 3 and after stage 2's result is read,
and recorded in the change log:

- Python, open source under a permissive license, with `pytest` tests that run
  from a checkout in under 10 minutes, so the oracle is cheap;
- at least 200,000 lines of non-test Python, measured and recorded at the
  pinned commit (hermes-agent is about a million);
- at least 60 commits whose subject starts with `fix` and that change 1–3
  source files and at least one test, committed after the pinned model's
  training cutoff, so the walk can find 20 that qualify;
- a `profiles.py` entry committed with the pinned commit.

Candidates to measure against that rule, in no order: `BerriAI/litellm`,
`ansible/ansible`, `sqlalchemy/sqlalchemy`, `home-assistant/core` (the
largest and best-tested, and the heaviest test environment). None is chosen
here.

## Publication

- `bench/task_outcome/unfamiliar-repo/`: `runs.jsonl`, the three blocks'
  offline accuracy, and `analyze`'s report, committed whatever the result,
  labelled "pilot" as the main spec labels a first run of 20 tasks.
  Transcripts stay out of git; each run records its transcript's SHA-256.
- The keyword hook, its tests and its index format are in the repository
  before stage 1, so the free arm can be rerun by anyone.
- A supported sentence quoted on the site gets a `site/claims.json` entry
  naming this spec and the command that reproduces it, and says it was
  measured on one repository until stage 3 completes.
- A null result is published with the same prominence, and the honest
  assessment and the business case are updated to cite it in the same change.

## Threats to validity, stated up front

- **One repository, again.** Stage 3 exists for this. Until it runs, a
  supported sentence names hermes-agent.
- **The keyword hook is our implementation of the assessment's baseline.**
  The assessment's scripts are not public, so this hook is written from its
  description (BM25 over names and docstrings, top five). Its offline
  accuracy on these tasks is published before any run so that a reader can
  judge whether it is a fair stand-in. A weak implementation would make
  comparison B easier to pass, not harder, so it is held to the assessment's
  own figures.
- **The prompts were written from the fix.** They may quote identifiers more
  faithfully than a user's bug report, which favours lexical matching in both
  hooks. All three arms get the same prompts, so the comparison is fair; the
  size of any effect may not transfer.
- **Five of the twenty tasks tuned the ranking.** Reported separately, as
  above.
- **Cost at API prices on a subscription login** measures relative usage,
  not a bill. The same for every study here.
- **The agent may read the block and search anyway.** That is a finding, not
  a flaw, and the mechanism endpoints show it.
- **Contamination.** Tasks are commits after 2026-09-15. If the pinned model's
  training data could include them, the run is flagged in the change log.
- **What this does not measure:** learning over time (the memory track), the
  MCP tools (never called in any Claude Code study), and any benefit on a
  repository the agent already knows.

## What is not in this track, and why

- **A governance or compliance endpoint.** NeuralMind's audit log, SBOM and
  provenance are evidence about NeuralMind's own calls and build; they do not
  change what an agent does on a task, and they are not what an enterprise
  evaluator's trial measures. They are documented in
  [`COMPLIANCE-SUMMARY.md`](../COMPLIANCE-SUMMARY.md) and are not a claim
  this track can support or refute.
- **SSO, seat management, cross-machine sync.** Roadmap items with no bearing
  on whether the agent benefits. They are not marketed
  (`commercial-terms.json`, `do_not_market`).
- **Time to onboard a developer.** The buyer's question, but it has no cheap
  oracle. Tool calls before the first read of a gold file is the nearest
  measurable proxy and is reported as mechanism.

## Change log

- 2026-11-06 — draft written, after the independent assessment of 4.24.0
  (2026-11-03) and track 1's stage 0b (2026-11-03). Not pre-registered: no
  task list, pin or analysis code is committed for it yet, and the keyword
  hook does not exist. Open before registration: whether track 1's floor
  check has replaced any task; the NeuralMind release to pin; the Claude Code
  sign-in the Mac will use.
- 2026-11-07 — from review on the draft's PR, before registration: the "A
  passes, B does not" branch no longer asserts that the keyword hook gives the
  same help; that sentence now needs a pre-specified equivalence margin (B's
  interval within ±5%, solve counts within one). And a null result is read by
  its interval against a fixed 10% threshold, not by the power calculation.
