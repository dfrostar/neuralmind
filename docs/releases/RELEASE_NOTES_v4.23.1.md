# NeuralMind v4.23.1 — the Hermes plugin serves each session's own project under Hermes 0.22's gateway, and a first turn's recap arrives within the timeout

**Type:** Patch release | **Theme:** on Hermes 0.22.2 and later, CLI, TUI and Desktop sessions get their project's context again, and on a large repository a session's first turn gets the previous session's recap

Since Hermes 0.22.2, the hooks of every local session (CLI, TUI and Desktop)
run in one Hermes gateway process, not in the `hermes` command you start. That
process's own working directory and environment belong to no session. Hermes's
plugin guide says so, and gives plugins `ctx.session_cwd()` for the calling
session's working directory instead.

The NeuralMind plugin didn't ask for it. Unpinned, it served the first built
project among `NEURALMIND_PROJECT`, `TERMINAL_CWD` and the current directory,
all read from the gateway's own environment. On a 32-core Linux machine running
Hermes 0.22.5, the gateway's `TERMINAL_CWD` was the user's home directory,
which isn't a built project. So every `hermes chat` turn in a built
hermes-agent checkout got **no NeuralMind context at all**: no recall block,
and no recap on a session's first turn. The plugin also wrote nothing for the
session and logged no warning. Setting `NEURALMIND_PROJECT` on the command
didn't help: the variable stayed in the client process.

The second fix is for a session's first turn on a large repository. v4.23.0
made the per-prompt hook fast on a large index, so on hermes-agent the
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
stopped the export, and which, on Hermes 0.22.2 and later, never reached the
hooks when set on the `hermes` command.

---

## What changed

### Under the gateway, the plugin follows the session's working directory

- **Which project, in order:**
  1. `NEURALMIND_PROJECT`, if set where the plugin runs;
  2. else the project pinned at install;
  3. else the directory Hermes works in for the session.

  The first of these that has been built wins, as before.
- **"The directory Hermes works in" is now `ctx.session_cwd()`** whenever
  Hermes provides it (0.22.2 and later). That's where the CLI, TUI or Desktop
  session was started, or, for a messaging chat, the profile's terminal
  working directory.
- **A session with no working directory gets nothing.** Hermes reports that
  as an empty string. The plugin then doesn't fall back to the gateway's own
  directory or `TERMINAL_CWD`, which are shared by every session.
- **Recorded edits and reads** that Hermes reports by a relative path resolve
  against the same session directory.
- **Older Hermes is unchanged.** It runs hooks in the client process, where
  `TERMINAL_CWD`, else the current directory, is still the rule.

### `NEURALMIND_PROJECT` counts only where the hooks run

Under the gateway, setting `NEURALMIND_PROJECT` (or any NeuralMind switch, such
as `NEURALMIND_SYNAPSE_EXPORT`) on the `hermes` command you start doesn't reach
the plugin. Only the gateway's own environment does, and there it applies to
every session, like a pin. The docs that said to set it for Desktop, ACP and
per-session workspaces now say this instead.

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

---

## What the agent sees post-install

| Agent | Before v4.23.1 | From v4.23.1 |
|---|---|---|
| **Hermes-Agent plugin**, Hermes 0.22.2+, unpinned | No NeuralMind block or recap in CLI, TUI and Desktop sessions, unless the gateway's own `TERMINAL_CWD` or working directory was a built project, and then every session got *that* project's | Each session gets its own project's block, and its recap on its first turn, when its working directory is built |
| **Hermes-Agent plugin**, any version, large store | A session's first turn could lose the recap: the `session-start` call was stopped at 8 s. `NEURALMIND_SYNAPSE_EXPORT=0` avoided it, where it reached the hooks | The recap arrives: the call returned in 0.18–0.62 s on an M3 and 2.0–3.6 s on the Linux machine, and the decay tick and export finish in the background |
| **Hermes-Agent plugin**, older Hermes or pinned | Followed `TERMINAL_CWD`, or the pin | Unchanged |
| **Claude Code** (`SessionStart` hook) | Session start waited for the decay tick and the export (4–8 s on a 1.27M-edge store) before the first prompt | Session start no longer waits for them. On a store of 64 MB or more, `SYNAPSE_MEMORY.md` is rewritten a few seconds after the hook returns, so a session may load the file the previous session start wrote |
| **Cursor, Cline, generic MCP** | No `SessionStart` hook or Hermes plugin; unaffected | Unchanged |

Claude Code reads `@.neuralmind/SYNAPSE_MEMORY.md` through `CLAUDE.md`, and
we haven't checked whether it loads the file before or after its
`SessionStart` hooks finish, so this release doesn't claim that a session sees
the export its own start writes, before or after the change.

---

## Measured

### Which project a Hermes session gets

Checked on one machine and one Hermes version, not benchmarked: a 32-core
Linux laptop running Hermes 0.22.5, with the plugin installed unpinned. The
session ran in a built clone of hermes-agent, and the model was a local
`gpt-oss:20b-64k` served by Ollama.

| | v4.23.0 plugin | This change |
|---|---|---|
| NeuralMind hook processes a `hermes chat` turn started in its first 40 s | 0 | 2: `session-start` at 2.6 s, `prompt-submit` at 10.6 s |
| A recap file for the session in the clone's `.neuralmind/recaps/` | none | written |
| The NeuralMind block in the user message Hermes sent the model | absent (2 turns checked) | present (1 full turn, 582 s on CPU) |

- **The gateway kept the old plugin code until it reloaded its plugins.**
  `hermes plugins disable neuralmind && hermes plugins enable neuralmind` did
  that; replacing the plugin file alone didn't.
- **The first turn's `session-start` call was stopped at 8 s once.** That was
  the gateway, running with the memory export on: `NEURALMIND_SYNAPSE_EXPORT=0`
  had been set only on the `hermes` command. The session-start change in
  this release, which moves that hook's slow work out of the call, covers
  that. The plugin logs each kind of warning once per process, so the log
  can't show whether the later full turn's call was stopped too.
- **This change is about delivery, not ranking.** For the full turn's wording
  ("which file in this repo decides whether it is a rate limit or a context
  overflow?") the block listed `agent/auxiliary_client.py` first and not
  `agent/error_classifier.py`, the file the real fix changed. The model named
  the file the block listed.

### A session's first-turn recap

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

**On the Linux machine** where 6.3–7.7 s was seen (32 cores, Hermes 0.22.5,
the 1,272,023-edge store, the memory export on), through the installed
plugin's own `pre_llm_call` at its default 8 s, with a recap to return:

| Linux, first turns (`session-start` + `prompt-submit`) | Time | Recap delivered |
|---|---|---|
| v4.23.0, eight busy loops | 8.5–10.6 s (3 turns) | 3 of 3, each call just under 8 s |
| v4.23.1, idle | 2.0–2.1 s (4 turns) | 4 of 4 |
| v4.23.1, eight busy loops | 2.4–3.6 s (4 turns) | 4 of 4 |

The detached process finished 4.1 s (idle) and 5.8 s (busy) after the call
began, and each time the decay tick had advanced `meta.last_decay` and the
export had rewritten `SYNAPSE_MEMORY.md`. At a load of 10–12, before this
change, a first turn took 12.0 s and its `session-start` call was stopped.
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

## Tests

`tests/test_hermes_plugin.py` checks that:
- `register()` keeps Hermes's plugin context;
- under the gateway, the session's working directory is the project, ahead of
  a built `TERMINAL_CWD` and a built gateway working directory;
- a session with no working directory (`""`, blank or `None`), or whose
  `session_cwd()` raises, gets no project and no hook call;
- `NEURALMIND_PROJECT` and a pin still come first;
- relative edit and read paths resolve against the session's directory.

The existing tests run as on older Hermes, where the plugin context has no
`session_cwd`.

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

## Upgrading

The session-start change is in the hook the plugin runs, so upgrading
NeuralMind is enough for it. The session-directory change is in the plugin,
which is a copy, so re-run the installer too:

```bash
pip install -U neuralmind
```

```bash
neuralmind install-hermes-plugin
```

A Hermes gateway that's already running keeps the plugin code it loaded. Reload
it:

```bash
hermes plugins disable neuralmind && hermes plugins enable neuralmind
```

That printed *Gateway reloaded plugins* on Hermes 0.22.5; restarting the
gateway works too. If you set `NEURALMIND_PROJECT` or
`NEURALMIND_SYNAPSE_EXPORT=0` on the command you start Hermes with, you can drop
them: on Hermes 0.22.2 and later they never reached the plugin, and from this
release it doesn't need them.

## Use cases

- **Existing: [NeuralMind in Hermes](../use-cases/hermes-agent.md).** One
  unpinned install serves every built project you open a Hermes session in, on
  Hermes 0.22.2 and later. Before, it usually served none.
- **Potential: one Hermes setup across several repositories.** The gateway
  serves each session from that session's own directory, so, per Hermes's
  plugin docs, a TUI in one repository and a Desktop session in another each
  get their own project's context. Only `hermes chat` was checked live. Before,
  pins and `NEURALMIND_PROJECT` were the only way to get any context there,
  and both apply to every session.
