# Track 1: a small model on a big repository — the 20 tasks

Pre-registered in
[`TASK-OUTCOME-BIGREPO-SMALLMODEL.md`](../../../../docs/specs/TASK-OUTCOME-BIGREPO-SMALLMODEL.md)
("Stage 1 and 2 design, fixed now"). `tasks.json` is that design's task list,
assembled on 2026-11-05 before stage 1's first run, in the registered order:

| Tasks | From | Count |
|---|---|---|
| 1–12 | [`hermes-agent-test-ranking/heldout/tasks.json`](../../../../bench/task_outcome/hermes-agent-test-ranking/heldout/tasks.json) | 12 |
| 13–17 | [`hermes-agent-screen/tasks.json`](../hermes-agent-screen/tasks.json) | 5 |
| 18–20 | the first 3 qualifying tasks of [`lexical-anchoring/confirm/tasks.json`](../../../../bench/task_outcome/lexical-anchoring/confirm/tasks.json), named in the spec on 2026-11-03: `f94d72f7e8`, `ebf002cd3e`, `5381678d03` | 3 |

Each entry is copied unchanged from its source (prompt included). All 20 are
[NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent)
fixes from the seeded walk pinned at `710fa8a`, run with
`--repo <hermes-agent clone> --profile hermes-agent`.

The floor check (stage 1) may replace tasks only as the spec's "if it fails"
column says; a replacement list is committed here before stage 2's first run.
