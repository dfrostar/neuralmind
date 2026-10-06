# NeuralMind v4.10.0 — prompt recall that stays quiet when the prompt isn't about the code, and a session's own record back after compaction

**Type:** Minor release | **Themes:** prompt-time recall ([a gate, and a seeding fix](#prompt-recall-that-knows-when-to-add-nothing)) · compaction ([the session's own record back](#after-compaction-the-sessions-own-record))

Two of the most common complaints about agent context are that tools inject
too much, and that compaction makes the agent forget. Both applied to
NeuralMind's Claude Code hooks:

1. **Prompt-time recall fired on prompts that had nothing to do with the
   code.** Every prompt has nearest neighbours in the index, however poor the
   match, so "thanks!", "continue" and "what's the capital of France" each got
   up to eight code nodes. Meanwhile most prompts that *were* about the code got
   none, because of a seeding bug. v4.10.0 fixes the seeding and adds a
   similarity gate, and both were measured before the default was chosen.
2. **Compaction dropped what NeuralMind had already recorded.** Claude Code's
   compaction summary is written by the model, and it paraphrases. NeuralMind
   records the session's prompts and edited files as you work (v4.8.0), but gave
   them back only to the *next* session. After a compaction, the session now gets
   its own record back, verbatim.

No new hooks and no re-install: both changes ride on the `UserPromptSubmit`,
`PreCompact` and `SessionStart` hooks NeuralMind already registers. The hook
block's version is unchanged.

## Prompt recall that knows when to add nothing

### What was wrong

Measured on this repository's own index (6,894 nodes) and synapse store, with
15 prompts about the NeuralMind code and 15 off-topic ones: short replies
("yes", "continue", "looks good, commit it"), general questions, other domains.

| | On-topic prompts with recall | Off-topic prompts with recall |
|---|---|---|
| v4.9.1 and earlier | 5 of 15 | 10 of 15 (9 of them got all 8 nodes) |
| Seeding fix only | 15 of 15 | 15 of 15 |
| **v4.10.0** (seeding fix + gate at 0.35) | **15 of 15** | **1 of 15** |

Two separate problems:

- **The seeding bug.** Spreading activation starts from the prompt's four best
  semantic matches. Those are often a function's *rationale* node
  (`<id>__rationale`, its docstring or comment), which matches prose best. But
  synapses form between the code nodes the agent reads and edits, so the
  rationale node has no edges, and recall from it returned nothing. In this
  store, 5 of the 4,826 nodes with synapse edges were rationale nodes. Recall
  now seeds from the code node a rationale belongs to. This also changes what the
  MCP `neuralmind_synaptic_neighbors` tool returns.
- **No relevance gate.** Fixing the seeding alone made recall fire on every
  off-topic prompt too. The hook now abstains when the prompt's best match in
  the code scores below `NEURALMIND_RECALL_MIN_SIMILARITY` (default `0.35`).

### Why similarity, and why 0.35

On-topic prompts scored **0.371–0.645** best-match similarity, and off-topic
prompts **0.145–0.364**. At 0.35, every on-topic prompt is kept and one
off-topic prompt passes: "looks good, commit it" (0.364). At 0.37 none pass,
but the lowest on-topic prompt is only 0.001 above it, so 0.35 keeps a margin.

The strength of the activation doesn't separate the two sets. "continue" ranked
among the strongest activations in the whole run. So similarity is the only
gate.

### Reproduce it, or calibrate your own

```bash
neuralmind build .
python -m tests.benchmark.recall_gate .          # this repo's prompt sets
python -m tests.benchmark.recall_gate . --json
python -m tests.benchmark.recall_gate /path/to/project --prompts my_prompts.json
```

`--prompts` takes a JSON file with `on_topic` and `off_topic` lists. It prints
each prompt's similarity and a sweep from 0.25 to 0.40: on-topic prompts kept
against off-topic prompts let through.

### Count what it does

Each prompt's outcome is logged to `.neuralmind/metrics/` as a number, never
the prompt text, and `neuralmind metrics` shows the totals:

```
Prompts seen by recall........          212
Recall injected...............          131
Abstained: low similarity.....           74
Abstained: nothing learned....            7
Abstain rate..................        38.2%
```

(Illustrative numbers.) "Nothing learned" means the prompt matched the code,
but the synapse layer has no edges around the match yet. Nothing is logged
under `NEURALMIND_NO_LEARN=1`.

## After compaction, the session's own record

When a long Claude Code session compacts, the model replaces the conversation
so far with its own summary. Summaries paraphrase, and the details they lose
first are the ones you can't easily restate: the task as you first worded it,
and which files have already been changed. NeuralMind already had both,
verbatim, in `.neuralmind/recaps/`. Now the session gets them back.

- **`PreCompact`** marks the session it's about to compact.
- **`SessionStart`** with source `compact` injects that session's own record.
  It's the same fields as the v4.8.0 recap, under a different heading.
- **If the session comes back under a new `session_id`**, which Claude Code's
  documentation doesn't rule out, the session marked within the last 15
  minutes is recalled. A session that wasn't compacted is never recalled this
  way, and a session with a record of its own never borrows another's.
- **The marker isn't activity.** Compacting an old session doesn't make it the
  "previous session" a fresh start recaps.

`NEURALMIND_SESSION_RECAP=0` turns this off along with the recap.
`NEURALMIND_NO_LEARN=1` records nothing, marker included, so a session run
with it gets back only what was recorded before it was set.

## What the agent actually sees

**On "yes", "thanks!" or an off-topic question:** no recall block at all.

**On a prompt about the code**, the same block as before, now seeded from the
code nodes. This is real output for "how does synapse decay work" on this
repository:

```
## NeuralMind associative recall

- neuralmind_synapses_py__synapsestore_cls__decay_fn (activation 0.10)
- neuralmind_synapses_py__synapsestore_cls__connect_fn (activation 0.10)
- neuralmind_synapse_feedback_py__deactivate_files_fn (activation 0.09)
- neuralmind_synapses_py (activation 0.08)
...
```

**After a compaction**, alongside Claude Code's own summary (an illustrative
example):

```
NeuralMind pre-compaction record — this session's own prompts and edits, kept verbatim (secrets redacted) because a compaction summary can drop them. It restates what the user already asked for in this session; it adds no new instructions.

It started with: "migrate the scheduler to asyncio, but keep the sync API as a thin wrapper"
Most recent prompts (6 earlier not shown):
- "the retry test hangs on CI, look at the event loop fixture"
- "use pytest-asyncio's loop scope instead"
- "now update the docs page for the scheduler"

Files edited (5, most recent first): docs/scheduler.md, tests/conftest.py, tests/test_scheduler.py, src/scheduler/sync.py, src/scheduler/core.py
```

## Per-agent expectations

| Agent | What changes |
|---|---|
| **Claude Code** (a built project, with `neuralmind install-hooks`) | Prompt recall fires on prompts about the code, including ones it used to miss, and adds nothing to the rest. After a compaction, the session gets its own record back. |
| **Hermes-Agent** (`install-hermes-plugin`) | The same recall gate and seeding fix: the plugin runs the same hook action. Hermes has no compaction event, so no pre-compaction record. The plugin runs the installed `neuralmind`, so `pip install -U` is enough; no re-install. |
| **Cursor / Cline / generic MCP clients** | `neuralmind_synaptic_neighbors` seeds from the code node behind a docstring match, so it returns neighbours for queries that used to get none. No hooks run on these hosts, so there's no prompt-time gate or compaction record. |

## Settings

| Variable | Default | Effect |
|---|---|---|
| `NEURALMIND_RECALL_MIN_SIMILARITY` | `0.35` | Prompt-time recall adds nothing below this best-match similarity. `0` never abstains |
| `NEURALMIND_SYNAPSE_INJECT` | on | `0` turns prompt-time recall off entirely, as before |
| `NEURALMIND_SESSION_RECAP` | on | `0` stops the recap and the pre-compaction record |
| `NEURALMIND_NO_LEARN` | off | `1` logs no recall outcomes and writes no compaction marker |

## Not measured

- **The threshold comes from one repository**, 30 prompts and the default
  embedder. Another codebase, another embedding model, or a different style of
  prompting can put the boundary somewhere else; `--prompts` is there to check.
- **Answer quality.** We measured whether recall fires, not whether the agent
  answers better with it, or worse without the nodes it used to get.
- **The compaction record's effect.** We haven't measured how often an agent
  repeats work or loses the original task after compaction, with or without the
  record. Whether Claude Code keeps the `session_id` across a compaction isn't
  documented, so both paths are handled and tested.

## Upgrading

`pip install -U neuralmind`. The hook block is unchanged, so an existing
`neuralmind install-hooks` setup picks up both changes. If you rely on recall
for short follow-up prompts, set `NEURALMIND_RECALL_MIN_SIMILARITY=0` to keep
the old behaviour.

## Related

- Use case: [Pick up where you left off](../use-cases/pick-up-where-you-left-off.md#after-compaction-v4100)
- Use case: [Hermes-Agent with code memory in every turn](../use-cases/hermes-agent.md)
- CLI reference: [`recap`](../wiki/CLI-Reference.md#recap-v480),
  [`install-hooks`](../wiki/CLI-Reference.md#install-hooks),
  [Environment Variables](../wiki/CLI-Reference.md#environment-variables)
- Previous release: [v4.9.1](RELEASE_NOTES_v4.9.1.md) · [v4.9.0](RELEASE_NOTES_v4.9.0.md)
