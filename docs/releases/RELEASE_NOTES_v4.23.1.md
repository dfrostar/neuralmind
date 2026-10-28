# NeuralMind v4.23.1 — the session-start hook returns its recap within the Hermes plugin's timeout on a large synapse store

**Type:** Patch release | **Theme:** a Hermes session's first turn gets the previous session's recap on a large repository, without turning off the memory export

v4.23.0 made the per-prompt hook fast on a large index, so on hermes-agent the
Hermes plugin got its block within the default 8 s: 2.5–3.9 s a turn on a
32-core Linux machine under load. A session's first turn makes one more call:
the plugin runs `neuralmind _hook session-start` for the previous session's
recap, as a separate process with its own 8 s limit
(`NEURALMIND_HERMES_TIMEOUT`). That call still overran there. It took 6.3–7.7 s
on a freshly rebuilt hermes-agent index (337,346 nodes, 1,272,023 synapse
edges), and Hermes's log said *`neuralmind _hook session-start` took longer
than 8.0s and was stopped*.

The recap itself was quick. The hook wrote it first, then ran a synapse decay
tick and the `SYNAPSE_MEMORY.md` export over the whole store: under a profiler
those were about 6 s of the call (the export's hub and strongest-pair queries
4.2 s, the decay tick 1.9 s). When the plugin stops a call, it drops
everything the call wrote, so the recap was thrown away with the rest. The
workaround was starting Hermes with `NEURALMIND_SYNAPSE_EXPORT=0`, which also
stopped the export.

---

## What changed

### On a large store, the decay tick and the export run after the hook returns

- **Below 64 MB of `.neuralmind/synapses.db`, nothing changes.** The hook runs
  the decay tick, the team-memory import, the selector auto-tuner (opt-in,
  `NEURALMIND_SELECTOR_AUTOTUNE=1`) and the export itself, so
  `SYNAPSE_MEMORY.md` is on disk before it returns. This repository's own
  13 MB store takes 0.1 s of it on an M3.
- **At 64 MB or more, a detached process does that work.** The hook writes the
  recap, clears the session's scratch state, starts
  `python -m neuralmind.session_maintenance <project>` and exits. The process
  runs the same steps in the same order, under the same environment switches
  (`NEURALMIND_NO_LEARN`, `NEURALMIND_SYNAPSE_EXPORT`, `NEURALMIND_TEAM_MEMORY`,
  `NEURALMIND_SELECTOR_AUTOTUNE`). Its output goes nowhere, so neither the
  plugin nor Claude Code waits for it, and only one runs per project at a time.
  If it can't be started, the hook skips the work rather than doing it itself.
  The next session's tick then applies the decay owed, because a tick decays
  each edge by the time since the previous tick, not by a fixed step.
- **The session-boundary resets stay in the hook.** Clearing the `ephemeral`
  namespace and forgetting the previous session's last-touched file still
  happen before the session's first tool call. They used to run after the
  decay tick and now run before it; the order doesn't change what either one
  leaves.
- **The store and the export come out the same.** With the clock pinned, the
  previous code, the in-hook path and the detached path leave byte-identical
  database dumps and `SYNAPSE_MEMORY.md` files (bar its *Updated* timestamp),
  on a store with `personal`, `shared`, `ephemeral` and branch rows and
  transitions.

The size limit is on the file, which also holds the build's structural tables
(about 300 MB of hermes-agent's store), so a store with few learned edges but a
large code graph is maintained in the background too. That costs nothing but
the few seconds before the file is rewritten. A store under 64 MB holds at most
about 115,000 synapse edges; one that size took 0.44 s on an M3.

## What the agent sees post-install

| Agent | Before | After |
|---|---|---|
| Hermes-Agent (plugin) | On a large store, a session's first turn could lose the recap: the `session-start` call was stopped at 8 s. `NEURALMIND_SYNAPSE_EXPORT=0` avoided it | The recap arrives: on a 1.27M-edge store the call returned in 0.18–0.62 s on an M3, and the decay tick and export finish in the background |
| Claude Code (`SessionStart` hook) | Session start waited for the decay tick and the export (4–8 s on a 1.27M-edge store) before the first prompt | Session start no longer waits for them. On a store of 64 MB or more, `SYNAPSE_MEMORY.md` is rewritten a few seconds after the hook returns, so a session may load the file the previous session start wrote |
| Cursor, Cline, generic MCP | No `SessionStart` hook; unaffected | Unchanged |

Claude Code reads `@.neuralmind/SYNAPSE_MEMORY.md` through `CLAUDE.md`, and
we haven't checked whether it loads the file before or after its
`SessionStart` hooks finish, so this release doesn't claim that a session sees
the export its own start writes, before or after the change.

---

## Measured

`tests/benchmark/session_start_latency.py` runs one fresh
`neuralmind _hook session-start` process per sample, with a recap to return,
and times it from start to exit, as the agent waits for it (*hook*). It also
times from the same start until the store work is finished (*done*): when the
detached process releases its lock, or, when there is none, when the hook
exits. 5 samples each, on an M3 MacBook (8 cores), once idle and once with six
busy loops running (`yes > /dev/null`).

**The store.** The hermes-agent store behind held-out task `0cb3760383`'s index
(built by v4.22.1) has 474,232 synapse edges, all structural. It was scaled to
the reported machine's 1,272,023 edges: its structural edges copied under
renamed node ids (1,192,985), plus 79,038 `personal` edges with random weights
and ages up to 30 days, 7,904 transitions and 51,919 node activations; 1.07 GB.
The learned rows are synthetic, so this measures how long the work takes on a
store of that size, not what a real one's export says. The recipe is in the
raw results.

| 1,272,023 edges, M3 | hook: mean | hook: range | hook under 8 s | done: mean | done: range |
|---|---|---|---|---|---|
| v4.23.0, idle (load average 2.5) | 4.34 s | 4.12–5.19 s | 5 of 5 | 4.34 s | 4.12–5.19 s |
| v4.23.1, idle (2.3) | 0.20 s | 0.18–0.22 s | 5 of 5 | 4.39 s | 4.16–5.18 s |
| v4.23.0, six busy loops (6.3) | 7.00 s | 6.70–8.03 s | 4 of 5 | 7.00 s | 6.70–8.03 s |
| v4.23.1, six busy loops (8.2) | 0.33 s | 0.25–0.62 s | 5 of 5 | 7.48 s | 6.87–8.21 s |

Every sample returned the same 406-character recap. The work takes as long as
it did; the hook no longer waits for it. Under a profiler (idle, v4.23.0) the
hook's 3.96 s was 3.49 s of export (the hub query 2.12 s, the strongest pairs
1.19 s) and 0.44 s of decay tick, and those passes are untouched here.

**A Hermes first turn on that store.** With the graph cache written, the
`prompt-submit` call that follows took 1.36–1.43 s when it ran right after
`session-start`, with the detached process running beside it, and 1.34–1.38 s
on its own, returning the same block (3 calls each, idle). The first turn's
two calls come to about 1.6 s, against about 5.7 s with v4.23.0's
`session-start`.

**Not yet timed on the Linux machine** where 6.3–7.7 s was seen; there, the
old hook spent about 6.0 s in SQLite, the work the detached process now does.
One store, one machine; the numbers say how much of the call the store
work was, not how long it takes elsewhere. Raw results:
`bench/hook_latency/session-start-hermes-agent-1.27M-m3.json`.

Reproduce, from a source checkout, on a **copy** of a project with a synapse
store (the hook writes to it, as a session start does; on APFS `cp -cR`
clones a large index instantly):
`python -m tests.benchmark.session_start_latency <project-copy> --runs 5`;
for an older NeuralMind, put its checkout on `PYTHONPATH`.

### What it doesn't change

- The decay tick still rewrites every learned edge in one write transaction
  (0.44 s of the M3 run above). A tool-call hook that records an edit while it
  runs waits for it, as SQLite writers wait for each other; recall only reads,
  and doesn't wait.
- The export's queries are the same. Making them cheaper (a degree table for
  the hub list, say) would change what has to stay consistent with every
  write, for work that no longer holds anyone up.

### Tests

- `tests/test_session_maintenance.py`: a small store is maintained in the hook;
  a large one is left to a detached process with its stdio on `/dev/null` and
  its own session, while the hook still emits the recap and makes both
  session-boundary resets; the detached path leaves the same database and
  export as the in-hook one, with the clock pinned; the module runs as
  `python -m`; a real hook process with every store counted as large returns
  the recap and the detached process writes the export; a second process leaves
  the work to the first; `NEURALMIND_NO_LEARN=1` exports without decaying;
  nothing starts when there's nothing to do; a process that can't start is
  skipped, not run in the hook.
- `tests/test_session_start_latency_benchmark.py`: the benchmark tells a
  detached process's end from no process.

### Upgrading

Nothing to do. The change is in the hook the Hermes plugin runs, not in the
plugin, so upgrading NeuralMind is enough; `neuralmind doctor` reports an
installed plugin older than NeuralMind until you re-run
`neuralmind install-hermes-plugin`, as after any release. If you set
`NEURALMIND_SYNAPSE_EXPORT=0` only to get the recap through, you can drop it.
