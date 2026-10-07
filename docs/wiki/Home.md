<!-- neuralmind:example-file — annotations here are syntax examples, not evidence. -->
# 🧠 NeuralMind Wiki

**Persistent, local-first codebase memory for AI coding agents.** A semantic code graph + a synapse layer that learns how you work + an MCP server, Claude Code hooks and a Hermes-Agent plugin — for Claude Code, Hermes-Agent, Codex, Cursor, Cline, Continue, and any MCP client. On the public benchmark: 95% mean gold-file recall at 45–246× fewer tokens than pasting every source file.

Welcome — this wiki is the in-depth reference. For the fastest orientation, use the two pages at the top of Quick Links.

## Why NeuralMind — what the data shows, losses included

NeuralMind is more than token reduction. Every claim below ships with a
committed eval. The first two run on **real, pinned OSS repos** and are fully
reproducible — `python -m evals.public.run` for the four-repo benchmark,
`python -m evals.public.competitor` for the `requests`/`click` competitor
head-to-head. The last two are measured A/Bs on the bundled **reference
fixture**, so they're real but smaller-scope — and the last one is currently
a loss, published as such.

| | Benefit | Measured result | Where it's measured |
|---|---|---|---|
| 💸 | **Cheaper context** | **85.71–100% gold-file recall (95% mean) at 45–246× fewer tokens** than pasting every source file — beats `ripgrep` on cost on every repo, and on recall beats it on 3 of 4 and ties exactly on the fourth | Public benchmark, **real OSS repos** (`requests`, `click`, `flask`, `rich`) |
| 🎯 | **Finds the *right* code, not just less of it** | **100% gold-file recall, MRR 0.96** — ranks the correct file at the top; beats the incumbent `codebase-memory-mcp` on retrieval ranking (0.96 vs 0.23) | Competitor head-to-head, **real repos** (`requests`, `click` only — off by default, not yet re-run on the four-repo corpus) |
| 🧠 | **Learns how you work** | A Hebbian *synapse* layer that learns co-edited files lifts top-k retrieval hit-rate — **+3.5 to +14 points across runs**, CI-gated on direction — **budget-neutral** (no extra tokens) | Synapse A/B eval (**reference fixture** — smaller scope) |
| 🔬 | **Answer grounding vs. naive truncation — a published loss** | At a *matched* token budget, naive truncation currently keeps slightly more gold facts on this prose-heavy fixture: **delta −0.054 at v4.3.4** (earlier releases +0.013 to +0.143). CI fails the build below **−0.10** | Faithfulness gate (**reference fixture** — smaller scope) |

*Honest scope:* the **cost** and **accuracy** rows run on real, pinned OSS repos
(fully reproducible — see [methodology](https://github.com/dfrostar/neuralmind/blob/main/docs/benchmarks/public.md)); the "beats ripgrep" claim is specifically
against ripgrep — a bare vector-RAG baseline matches or beats NeuralMind's recall at fewer
tokens, see ["Where NeuralMind loses"](https://github.com/dfrostar/neuralmind/blob/main/docs/benchmarks/public.md#where-neuralmind-loses);
the **learning** and **grounding** rows are
committed A/Bs on the bundled reference fixture, so they're real but
smaller-scope. We report where NeuralMind *doesn't* win too — a well-tuned
vector RAG matches or beats it on pure findability and is cheaper on raw tokens;
that's in the benchmark table. The competitor comparison is *pure retrieval ranking*, not
their LLM-agent loop. Full numbers and reproduction commands on the
**[Benchmarks](Benchmarks)** page.

## What's New

### v4.10.0 — Hermes can install the NeuralMind plugin itself, and the plugin says why when it can't work (October 2026)

The Hermes plugin's directory now carries its own `plugin.yaml` (declaring
`requires_hermes: ">=0.21.5"`) and a
[README](https://github.com/dfrostar/neuralmind/blob/main/neuralmind/hermes_plugin/README.md)
that lists what it reads, writes and sends. So Hermes can install it from a
clone of this repository,
`hermes plugins install dfrostar/neuralmind#neuralmind/hermes_plugin --enable`,
and Hermes's catalog check, `hermes plugins validate`, passes. Installed that
way, the plugin runs the `neuralmind` command on Hermes's PATH (absolute PATH
entries only); `neuralmind install-hermes-plugin` on a plugin Hermes installed
writes only the interpreter and the project. When the plugin can't start
NeuralMind, finds one older than 4.9 (which answers without the session
recap), or a call times out, it logs one warning per Hermes process naming the
fix: `hermes logs --level WARNING | grep -i neuralmind`. Fixed:
`install-hermes-plugin --uninstall` disabled the plugin before removing it,
which left it on Hermes's disabled list, so installing it again left it off;
it now runs `hermes plugins remove neuralmind`, which drops its entries from
`config.yaml`. Tested against Hermes v0.21.5 in live `hermes chat` sessions.
[`install-hermes-plugin`](CLI-Reference#install-hermes-plugin-v490).

Also in v4.10.0, opt-in for Claude Code: NeuralMind's PostToolUse hooks inject
nothing by default, because Claude Code adds `additionalContext` next to a tool
result instead of replacing it. With `NEURALMIND_BASH_REPLACE=1`, the Bash
hook replaces one kind of output through `updatedToolOutput`: `pip install`
and `neuralmind build` run on their own reach Claude with their progress lines elided and every other line verbatim,
and a line mentioning an error, warning, failure or deprecation is never
removed. The full output, credentials redacted, is kept under
`.neuralmind/bash_outputs/`, and the replaced result ends with its path. Every
other command, failed commands, and Read and Grep results are never replaced.
The [compression benchmark](https://github.com/dfrostar/neuralmind/blob/main/docs/benchmarks/compression.md)
gates it in CI on keeping the pre-registered must-keep lines. Walkthrough:
[Trim noisy install logs](https://github.com/dfrostar/neuralmind/blob/main/docs/use-cases/claude-code.md#trim-noisy-install-logs-opt-in-v4100) ·
[release notes](https://github.com/dfrostar/neuralmind/blob/main/docs/releases/RELEASE_NOTES_v4.10.0.md).

Also in v4.10.0: `neuralmind validate` stops reporting the chapter files the
prose path records, such as `ch01.md`, as stale synapses while the index
still holds `chapters/ch01.md`, and the `neuralmind.sleep` API's long-term
promotion no longer boosts ephemeral edges, which decay never protects.

### v4.9.2 — `--` works again in the decisions and memory subcommands (October 2026)

v4.9.1 let six `decisions` and `memory` subcommands take the project path
after their options, but on Python 3.10, 3.11, 3.12 before 3.12.8 and 3.13.0
`--` could stop ending their options: `decisions query -- -q .` failed. `--` works again, the path can still follow the options, and every
supported Python parses these lines the same way. A path after a list option
such as `--evidence` needs `--` before it, which `record --help` and
`amend --help` now say.
[Release notes](https://github.com/dfrostar/neuralmind/blob/main/docs/releases/RELEASE_NOTES_v4.9.2.md).

### v4.9.1 — The last four fixes from the v4.8.2 bug hunt (October 2026)

`neuralmind feedback good|bad` with query memory off no longer adjusts an
older query recorded before memory went off; it exits 1, names that query and
says how to turn memory back on. The "LTP-protected" edge count in `status`,
`synapse stats` and the dashboard uses decay's own rule, so expect a lower
number. `neuralmind validate` stops reporting the prose path's query nodes,
now written `query:<term>`, as stale. And the `decisions` and `memory`
subcommands accept the project path after their options (`decisions restore
<id> --commit SHA <path>`) on every supported Python; on 3.10, 3.11, 3.12
before 3.12.7 and 3.13.0 that failed. (On those versions, and on 3.12.7, `--`
could stop ending their options; v4.9.2 fixes that.) None of the four lose
data.
[Release notes](https://github.com/dfrostar/neuralmind/blob/main/docs/releases/RELEASE_NOTES_v4.9.1.md).

### v4.9.0 — Hermes-Agent gets NeuralMind's context in every turn, without a tool call (October 2026)

On Hermes-Agent, NeuralMind used to be something the agent had to decide to
call, through the MCP server or a skill. `neuralmind install-hermes-plugin`
installs a Hermes plugin that adds context to every turn before the model runs:
the files and recorded decisions related to the user's message, the same block
Claude Code's `UserPromptSubmit` hook adds, and on a session's first turn the
recap. Hermes appends it to that turn's user message, not the system prompt.
Subagent and cron-job turns are skipped: they aren't recorded or answered with
recall, they don't run the `SessionStart` action, and their edits aren't
recorded. Files changed with `write_file` and `patch` are recorded at the
absolute paths Hermes reports, but only edits that landed: Hermes's status for
the call must be `ok`, so a cancelled, timed-out, blocked or failed edit isn't
recorded, and files a V4A patch deletes or moves away aren't listed as edited. Hermes and
Claude Code share `.neuralmind/recaps/`, so the recap carries over between the
two agents. A gateway session (Telegram, Discord …) uses the gateway's terminal
working directory (`terminal.cwd`, else `MESSAGING_CWD`, else your home
directory) unless a project is pinned at install or `NEURALMIND_PROJECT` is set;
whenever it resolves to a built project, pinned or not, every message in it is
recorded for the recap, credential-redacted, and `NEURALMIND_SESSION_RECAP=0`
turns that off. A pin applies to every Hermes session using that Hermes home,
in any directory (each gets the pinned project's context, its prompts are
recorded in that project, and a session in another repository also puts its
edited files' paths into the pinned project's synapse store, from where
`neuralmind memory publish` can carry them into the committed team-memory
bundle), so if you use Hermes across several projects, install without a path.
Unpinned, the plugin follows the directory Hermes works in, which it reads from
`TERMINAL_CWD` in the Hermes process's environment: that matches the terminal
CLI and a standalone gateway, but Hermes Desktop, ACP editor sessions and
per-session workspaces keep each session's directory elsewhere, so there, pin a
project or set `NEURALMIND_PROJECT`. Each call the plugin makes to NeuralMind
waits at most `NEURALMIND_HERMES_TIMEOUT` (default 8 seconds; a session's first
turn makes two), and one that times out or fails is left out while the turn
goes ahead. If the plugin runs past Hermes's `plugins.hook_callback_timeout`
(default 30 s), Hermes drops the whole block and skips the plugin for the next
60 seconds, so keep twice `NEURALMIND_HERMES_TIMEOUT` below it.
Tested against a Hermes v0.21.5 main-branch build by calling its plugin loader
and hook dispatch directly, not yet in a live Hermes conversation; what the
context changes in Hermes's answers isn't measured. Walkthrough:
[Hermes-Agent with code memory in every turn](https://github.com/dfrostar/neuralmind/blob/main/docs/use-cases/hermes-agent.md) ·
[`install-hermes-plugin`](CLI-Reference#install-hermes-plugin-v490) ·
[release notes](https://github.com/dfrostar/neuralmind/blob/main/docs/releases/RELEASE_NOTES_v4.9.0.md).

### v4.8.1 — Installers that can't destroy your config, the bug-hunt fixes, and a stricter `audit verify` (October 2026)

The high- and medium-severity bugs from an end-to-end bug hunt. `install-hooks`
and `install-mcp` no longer overwrite a config they can't parse; the Bash
output cache redacts what the AWS CLI prints; hooks act only in a project that
has `.neuralmind/` and follow the agent into subdirectories; and graph building, retrieval, the
CLI's numbers and synapse learning get their fixes. `neuralmind audit verify`
now fails on a record without a hash once the chain has started, on a line
that isn't a JSON object, and on a mismatched `prev_sha256`; v4.8.0 and
earlier passed all three. Run `neuralmind build` once after upgrading. See the
[release notes](https://github.com/dfrostar/neuralmind/blob/main/docs/releases/RELEASE_NOTES_v4.8.1.md).

### v4.8.0 — A new session starts where the last one left off; decision search by meaning; policy mistakes refused (October 2026)

A fresh or cleared Claude Code session now starts with a short recap of the
previous one in the project: its first prompt, its last three, and the files it
edited, labelled as context rather than instructions. The `UserPromptSubmit` and
Edit/Write hooks record them (prompts credential-redacted) in
`.neuralmind/recaps/`, and the `SessionStart` hook injects the recap; there is no
model call and no new hook. `neuralmind recap` shows what the next session will
see, `neuralmind recap --clear` deletes the records, and
`NEURALMIND_SESSION_RECAP=0` turns it off. Nothing about its effect is measured
yet. Walkthrough:
[Pick up where you left off](https://github.com/dfrostar/neuralmind/blob/main/docs/use-cases/pick-up-where-you-left-off.md)

On Hermes-Agent, NeuralMind used to be something the agent had to decide to
call, through the MCP server or a skill. `neuralmind install-hermes-plugin`
installs a Hermes plugin that adds context to every turn before the model runs:
the files and recorded decisions related to the user's message, the same block
Claude Code's `UserPromptSubmit` hook adds, and on a session's first turn the
recap. Hermes appends it to that turn's user message, not the system prompt.
Subagent and cron-job turns are skipped: they aren't recorded or answered with
recall, they don't run the `SessionStart` action, and their edits aren't
recorded. Files changed with `write_file` and `patch` are recorded at the
absolute paths Hermes reports, but only edits that landed: Hermes's status for
the call must be `ok`, so a cancelled, timed-out, blocked or failed edit isn't
recorded, and files a V4A patch deletes or moves away aren't listed as edited. Hermes and
Claude Code share `.neuralmind/recaps/`, so the recap carries over between the
two agents. A gateway session (Telegram, Discord …) uses the gateway's terminal
working directory (`terminal.cwd`, else `MESSAGING_CWD`, else your home
directory) unless a project is pinned at install or `NEURALMIND_PROJECT` is set;
whenever it resolves to a built project, pinned or not, every message in it is
recorded for the recap, credential-redacted, and `NEURALMIND_SESSION_RECAP=0`
turns that off. A pin applies to every Hermes session using that Hermes home,
in any directory (each gets the pinned project's context, its prompts are
recorded in that project, and a session in another repository also puts its
edited files' paths into the pinned project's synapse store, from where
`neuralmind memory publish` can carry them into the committed team-memory
bundle), so if you use Hermes across several projects, install without a path.
Unpinned, the plugin follows the directory Hermes works in, which it reads from
`TERMINAL_CWD` in the Hermes process's environment: that matches the terminal
CLI and a standalone gateway, but Hermes Desktop, ACP editor sessions and
per-session workspaces keep each session's directory elsewhere, so there, pin a
project or set `NEURALMIND_PROJECT`. Each call the plugin makes to NeuralMind
waits at most `NEURALMIND_HERMES_TIMEOUT` (default 8 seconds; a session's first
turn makes two), and one that times out or fails is left out while the turn
goes ahead. If the plugin runs past Hermes's `plugins.hook_callback_timeout`
(default 30 s), Hermes drops the whole block and skips the plugin for the next
60 seconds, so keep twice `NEURALMIND_HERMES_TIMEOUT` below it.
Tested against a Hermes v0.21.5 main-branch build by calling its plugin loader
and hook dispatch directly, not yet in a live Hermes conversation; what the
context changes in Hermes's answers isn't measured. Walkthrough:
[Hermes-Agent with code memory in every turn](https://github.com/dfrostar/neuralmind/blob/main/docs/use-cases/hermes-agent.md) ·
[`install-hermes-plugin`](CLI-Reference#install-hermes-plugin-v490) ·
[release notes](https://github.com/dfrostar/neuralmind/blob/main/docs/releases/RELEASE_NOTES_v4.8.0.md).

Decision search now ranks by meaning as well as by shared words, with the
local embedding model the code index already uses, so a question finds a
decision worded differently from it. `hybrid` is the default; `semantic` and
`keyword` are the other modes, and `NEURALMIND_DECISION_SEARCH=keyword` keeps
the old ranking. See [Memory Layer](Memory-Layer.md#query-decisions) and
[Find the decision behind the code when you don't know its words](https://github.com/dfrostar/neuralmind/blob/main/docs/use-cases/find-decisions-by-meaning.md).

Two mistakes in `neuralmind-backend.yaml` used to leave the default MCP role
policy in force, under which any caller can declare `admin` and reach every
tool: a file that doesn't parse, and a `security:` or `roles:` key left empty
(what's left when every entry under it is commented out). Both now refuse every
MCP call with `reason: "config"`. An unparseable file is refused only when it
names a security setting outside a comment, so a typo in backend tuning doesn't
block the server. `neuralmind doctor`'s *Security policy* check names the
setting to fix; see the
[Security Guide](https://github.com/dfrostar/neuralmind/blob/main/docs/SECURITY-GUIDE.md#capping-what-a-caller-can-claim).

### v4.7.0 — MCP roles bound to OS accounts, and a check for encrypted storage (October 2026)

`security.identity: os` takes each MCP caller's identity from the OS account
the server runs as, and its role from `security.users`, instead of trusting
the role a call declares. `security.require_encrypted_storage: true` refuses to
build, query, serve MCP tools or run hooks until FileVault, BitLocker or
dm-crypt/LUKS is verified. `neuralmind doctor` reports both. Nothing changes
for a project that doesn't set these keys. See the
[release notes](https://github.com/dfrostar/neuralmind/blob/main/docs/releases/RELEASE_NOTES_v4.7.0.md)
and the [CMMC CUI enclave walkthrough](https://github.com/dfrostar/neuralmind/blob/main/docs/use-cases/cmmc-cui-enclave.md).

### v4.6.0 — One keyword index for docs and code; the documented features wired in (October 2026)

The default backend's BM25 keyword index held only documents, so on "how does X
work" questions a doc kept taking the L3 slot the implementation should have
had. v4.6.0 indexes every node — doc text, symbol names, file paths,
docstrings — in one BM25 index, on by default (`NEURALMIND_BM25_UNIFIED=0`
restores v4.5.0). It was the one change of six that passed a keep rule fixed in
advance, on 30 questions per repo across six repos — pre-registered and
committed for the five public repos, plus a private 383-file repository
(`python -m evals.retrieval.run`; reproducible on demand, not a CI gate): mean
hit@5 **72.8% → 79.4%**, MRR 0.589 →
0.654, public-benchmark gold-file recall 93.75% → 95%, tokens +1.1%. Published
losses: `requests` drops one question, `rich`'s MRR falls 0.71 → 0.60, `click`
gains a public-benchmark miss, and a private 383-file repository reaches
73% / 0.60 against a target of 80% / 0.65 — not met. The other five changes
ship off by default behind flags, and `neuralmind query --explain` now prints
the query intent L3 ranked with. Run `neuralmind build` once after upgrading.
Walkthrough: [A/B-test a ranking change on your own repo](https://github.com/dfrostar/neuralmind/blob/main/docs/use-cases/ab-test-a-ranking-change.md) ·
[eval results](Benchmarks#retrieval-eval-v460)

Five features the docs had relabelled "not yet wired in" are settled. In Claude
Code, a **repeat read of an unchanged file** comes back as a short stub instead
of the whole file again (PostToolUse `updatedToolOutput`); the read after a
stub is always full, reads are tracked per session and subagent, and compaction
resets them (`NEURALMIND_READ_DEDUP=0` turns it off). **Decisions go stale on
commit**: `neuralmind init-hook .` runs `neuralmind decisions scan` after every
commit, marking STALE any decision whose file the commit changed after it was
recorded, and the stale-decision guard now shows why and how to restore one.
**Team governance is enforced**: `memory publish` honours the publishing scope
and weight threshold, `team governance remove-edge` retracts an association for
the whole team through the committed bundle, `list-shared` lists shared memory,
and publishes, imports and reviews are audited. The unused **co-access module
was removed**, and **`cognition-loop` was rebuilt** on the store's own decay
after its original pass turned out to delete learned memory; it stays on
demand. Walkthroughs:
[Keep decision memory honest across commits](https://github.com/dfrostar/neuralmind/blob/main/docs/use-cases/decision-memory-across-commits.md) ·
[Govern what your team's agents share](https://github.com/dfrostar/neuralmind/blob/main/docs/use-cases/govern-team-memory.md) ·
[release notes](https://github.com/dfrostar/neuralmind/blob/main/docs/releases/RELEASE_NOTES_v4.6.0.md).

### v4.5.0 — Numbers measured on your project (October 2026)

`neuralmind eval .` scores retrieval against questions and gold files you commit
in `.neuralmind.eval.yaml` — hit@1, hit@5, MRR, context tokens — and records
every run with its commit and version (`eval --report`). Measurement never
trains: `query --no-learn`, MCP `learn: false` and `NEURALMIND_NO_LEARN=1` read
the learned layer without writing to it, and `benchmark`, `probe` and `eval` are
read-only by default. Every reduction ratio now divides by the measured token
count of the code the index covers instead of a fixed 50K estimate, `probe`
samples stably across rebuilds, and the index covers what git covers —
`.gitignore` is honoured, including tracked files that match an ignore rule.
Walkthrough: [Measure retrieval on your own repo](https://github.com/dfrostar/neuralmind/blob/main/docs/use-cases/measure-retrieval-on-your-repo.md) ·
[release notes](https://github.com/dfrostar/neuralmind/blob/main/docs/releases/RELEASE_NOTES_v4.5.0.md).

### v4.4.0 — The index is never silently out of step with the code (October 2026)

A code graph that lags the code still "works" — it answers from code that no
longer exists. v4.4.0 makes that impossible to miss: `neuralmind doctor`,
`neuralmind health`, `neuralmind build` and the agent's first MCP wakeup compare
the graph with the files on disk in both directions, whatever tool built it
(new files the graph lacks, deleted files it still serves, a graph built on
another OS, files changed since — from `git diff` for a committed graph).
`neuralmind build . --regenerate-graph` escapes a stale graphify graph,
`graph_source: auto | builtin | graphify` pins the choice, every build purges
vectors for nodes that left the graph, and read commands load the index without
rebuilding it or printing a line. Walkthrough:
[Recover from a stale code graph](https://github.com/dfrostar/neuralmind/blob/main/docs/use-cases/recover-from-a-stale-graph.md) ·
[release notes](https://github.com/dfrostar/neuralmind/blob/main/docs/releases/RELEASE_NOTES_v4.4.0.md).

### v4.x — Decision memory and the stale-decision guard (September 2026)

NeuralMind now remembers *why* code is the way it is, not just where it lives.
**Decision memory** (v4.1.0) stores architecture decisions with rationale,
evidence, commit SHA and rejected alternatives — `neuralmind decisions record`,
`neuralmind decisions query`, `neuralmind decisions audit` — and you retire one
with `neuralmind decisions invalidate` when the code moves on (since v4.6.0 the
`init-hook` post-commit hook also retires them automatically). The
**stale-decision guard** (v4.2.0) is a `PreToolUse` hook that warns your agent
before it edits a file governed by a decision marked stale or invalidated
(fail-open; opt out with `NEURALMIND_STALE_GUARD=0`). Since v4.8.0, decision
search ranks by meaning as well as by shared words, with the local embedding
model, so a question finds a decision worded differently from it
([Memory Layer](Memory-Layer.md#query-decisions)). v4.3.0 adds progressive,
three-layer decision retrieval over MCP; v4.0.0 shipped the context budget,
session summaries and the on-demand `neuralmind cognition-loop` (rebuilt in
v4.6.0, which also wired read dedup into the Read hook and removed the unused
co-access module). The public benchmark was
regenerated at v4.3.4 with raw data committed: **93.75% mean gold-file recall
(85–100% per repo) at 45–261× fewer tokens** than pasting every source file <!-- claims-guard:allow — dated v4.3.4 and v4.6.0 figures, this line and the next -->
(superseded at v4.6.0: 95%, 46–263×; the ratios again at v4.10.0: 45–246×).
Guide: [Memory Layer](Memory-Layer).

### N-16 — Content QA System: Book/Markdown Retrieval (August 2026)

Extends NeuralMind from code-only to long-form content retrieval. Indexes 150K-word books via `neuralmind ingest-content` CLI. 30-query Underground manifest with graded relevance (0-3) per ~150-word chunk. N-15 IR metrics (recall@k, MRR, nDCG@5) + RAGAS faithfulness on compressed context. 7 CI regression gates with per-shape breakdowns (precise/thematic/entity/temporal/causal). Spec: [CONTENT-BENCHMARK-SPEC.md](../specs/CONTENT-BENCHMARK-SPEC.md).

### N-15 — SOTA Retrieval Quality Benchmarks (August 2026)

Graded relevance (0-3) + standard IR metrics (nDCG@5, MRR, recall@k, precision@k) + RAGAS faithfulness scoring on compressed retrieval output. 8 CI regression gates with per-shape breakdowns (focused/cross-file/identity). Zero-tolerance gate catches complete retrieval failures that averaged metrics hide. Consumes existing `ragas.py` stdlib-only judge — no embedding stack required. Spec: [RETRIEVAL-BENCHMARK-SPEC.md](../specs/RETRIEVAL-BENCHMARK-SPEC.md).

### N-13 — Business-Context Synapse Seeding (August 2026)

`seed_from_documents()` builds deterministic, LLM-free associations between business documents (decisions, SOPs, meeting notes, policies) and your code graph. Compound matches require adjacency in text (not just presence), title-reference cross-linking connects related business docs, and frequency-capped tags prevent common terms from dominating. 56 tests. This is the backbone of the "second brain" expansion (N-06 scope decision).

### v3.1.4 — Dogfood Fixes + Code/Document Scoring (August 2026)

v3.1.4 resolves all 12 dogfood issues from v3.1.2 and introduces **code/document scoring** for better retrieval precision.

**What's fixed:**
- P0: Role-gated tools, auto-rebuild hint, incremental build
- P1: `.neuralmindignore`, markdown bloat
- P2: Unknown edge relations, audit queries, SOC2, type filter, cross-project
- P3: Synapse pruning, health check endpoint

**What's new:**
- **Intent detection** — auto-detects code vs doc queries, boosts relevant nodes 2-3×
- **Health check** — `neuralmind health` with exit codes (0/1/2) for CI/CD
- **Synapse pruning** — `neuralmind synapse prune/stats` with LTP protection
- **Cross-project search** — `neuralmind query --projects a,b "question"`

Full details: [RELEASE_NOTES_v3.1.4.md](https://github.com/dfrostar/neuralmind/blob/main/docs/releases/RELEASE_NOTES_v3.1.4.md)

### v3.0.2 — Post-Extraction Cleanup (August 2026)

The self-improving loop (signal→insight→experiment→promote) was extracted to a private repo (`dfrostar/agencyOS`). NeuralMind is now pure code intelligence — the public package ships only what your agent needs.

- **Agent OS extracted.** 12 modules moved to `dfrostar/agencyOS`. The public repo is leaner.
- **Dashboard rebranded.** Agent/Agency OS references removed from ROADMAP and tests.
- **v3.0.0, v3.0.1** — SBOM publishing, license cleanup, extraction follow-through.

### v2.0.0 — Compliance Engine + `neuralmind init` (August 2026)

> **12–50× typical savings** — updated from the 12-50× estimate with founder-benchmarked results on local production repos. The original number was real vs a naive "dump all files" baseline (~30K tokens); 12–50× is the realistic range against a 10K-token human baseline. Up to 50×+ for targeted queries.

New compliance capabilities for regulated teams, plus a one-command project init.

| Feature | What |
|---------|------|
| `neuralmind init` | One-command project setup — auto-detects structure, installs hooks, builds index, all at once |
| Compliance annotation detection | Scans code **and docs** for annotations across CMMC 2.0, NIST SP 800-53, SOX ITGC, HIPAA, SOC 2 and ISO 27001. Each framework needs its own marker on the same line — `# NIST AC-1: …`, `# CMMC AC.L2-3.1.1: …`. `Compliance:` is a SOC 2 / ISO 27001 marker and does **not** match NIST ids; see [CLI-Reference](CLI-Reference.md#compliance-v314) |
| CMMC content ingestion | `neuralmind ingest-cmmc` imports CMMC 2.0 assessment guides + POA&M templates into the doc index |
| Audit export | `neuralmind export --controls` produces control-to-code mappings as CSV for evidence submission; `--format pdf` renders an SSP report |
| CI/CD compliance check | `neuralmind ci-check` gates builds on compliance annotation health |
| MCP tool | `neuralmind_compliance_report` — live compliance stance via any MCP-compatible agent |
| Savings recalibration | 12–50× typical (44× avg vs 30K naive baseline; 12–25× vs realistic 10K human baseline) |

**Claim tiering:**
- 44× avg vs 30K naive baseline — **Tier C** (self-measured, reproducible via `neuralmind benchmark .`)
- 12–25× vs realistic 10K human baseline — **Tier C** (self-measured, same pipeline)
- "Up to 50×+" for targeted queries — **Tier D** (hypothesized, depends on query shape)

### v1.7.1 — Schema hotfix + autopilot integration (July 2026)

Synapse schema fix adds `half_life_days` + `learned_at` columns before `CREATE TABLE` to fix `sqlite3.OperationalError` on existing databases. Autopilot v0.10.1 ships with self-improving loop (15-min systemd tick). Path migration from `/home/dtfrost/` to `/home/dtfrost5/`.

### v1.7.0 — Free tier auto-provision + upgrade funnel (July 2026)

Free tier now auto-provisions on first `wakeup`. `pip install neuralmind && neuralmind wakeup .` writes the license on first run — zero signup wall, zero "team" default breaking free onboarding.

- **Free tier auto-provision:** `cmd_wakeup` checks for `~/.config/neuralmind/license.json`; if missing, calls `issue_free_license()` and prints activation message
- **Default tier changed:** `Tier2Config.tier` default flipped from `"team"` to `"free"` — fresh `tier2.yaml` no longer triggers downgrade guard
- **Upgrade CTA:** Counter fires one-liner Team CTA at call 10 (NeuralMind Team: $29/user/mo — shared memory, governance, seat management)
- **Tests:** 21/21 tier2 tests pass, 191/191 total across tier2 + config + license-validator suites

Acceptance: free license created on first `wakeup`, idempotent on repeat calls, CTA fires exactly once at call 10.

### v1.4.0 — Louvain modularity clustering

`build_graph` now assigns communities via Louvain modularity over structural code-dependency edges. Previous versions assigned one community per file — every file in `src/auth/` was its own community even if it imported heavily from `src/users/`. v1.4.0 groups them: files with many inter-edges collapse into one community, isolated files (docs, configs) stay separate.

Stdlib-only pure-Python Louvain, O(n·k), deterministic output. 

Acceptance: 1582+ tests pass, `bench/` repos verify expected community counts.

### v1.0.0 — Team tier ships

NeuralMind Team is the paid tier for engineering teams of 5-50 seats: $29/user/mo, annual contract. Adds team memory governance, immutable audit log (SHA-256 hash-chained append-only), self-hosted deployment (docker-compose, one-command install), and seat management on top of the MIT core. Ed25519-signed license validation with 30-day offline grace. Acceptance: 46 unit + integration tests.

Full details: [RELEASE_NOTES_v1.0.0.md](https://github.com/dfrostar/neuralmind/blob/main/docs/releases/RELEASE_NOTES_v1.0.0.md)

### v0.52.0 — Impact: blast radius under a name you'd actually reach for

A Reddit comparison against GitNexus flagged "no `impact` tool" as a gap. Not quite right — `neuralmind structural --blast-radius` has answered "what depends on this?" since v0.42.0 — but the naming critique landed. v0.52.0 gives the same capability a name an agent (or a human) would actually reach for, plus richer output. Each dependent row now carries its **hop** and its **relation** (`calls`/`inherits`/`imports_from`/`implements`). The MCP tool is `neuralmind_impact()`. `structural --blast-radius` stays byte-identical — now a one-line wrapper over the same `blast_radius_detail()`. Honest scope: naming + discoverability, no new capability.

Full details: [v0.52.0 release notes](RELEASE_NOTES_v0.52.0.md) · [docs/use-cases/blast-radius-before-a-rename.md](https://github.com/dfrostar/neuralmind/blob/main/docs/use-cases/blast-radius-before-a-rename.md)

### v0.51.3 — Shipped

CI green, GitHub Release published, GHCR published, PyPI verified at 0.51.3.

Full details: [v0.51.3 release notes](RELEASE_NOTES_v0.51.3.md)

### v0.50.0 — Metrics Dashboard + Team Memory Integration

`neuralmind metrics --summary`, `--days`, `--json`, plus `/api/metrics` HTTP endpoint. Full team memory integration test (E1→E2→E3→E4 chain). Autopilot engine orchestrator + bug fixes (signals Page-Hinkley, self_play IDs, experiment_runner docstring).

Full details: [v0.50.0 release notes](RELEASE_NOTES_v0.50.0.md)

### v0.49.5 — DeepSeek Patches

Applied DeepSeek QA patches: prune dangling edges, remove dead code, fix axis independence in tuner faithfulness.

### v0.49.4 — DeepSeek QA

DeepSeek code review of incremental wiring, tuner, and autopilot modules. One CRITICAL finding (concurrent build locking — needs `fcntl.flock()`), two WARNING findings patched.

### v0.49.3 — Incremental Extraction Wiring

Wired `IncrementalExtractor` into `build_graph()` — scope re-extraction to changed files + importers. Acceptance: 10K-line repo, 1 file changed → <10% of full-build wall-clock.

### v0.49.2 — DeepSeek Wave 5 QA

DeepSeek review of tuner v0.49.0 and graphgen incremental wiring. CRITICAL: NaN/Inf guard, `_clamp()` does NOT defend against NaN. WARNING: inverted time filter in `_get_param_changes`. Patched.

### v0.49.0 — Tuner Faithfulness Gap

Live A/B eval: configure the embedder per candidate, run ~20 fixture queries, measure real retrieval_quality (nDCG@5) and session_health (re-query-rate).

### v0.48.0 — v2.0 Complete

All four waves of the v2.0 future-proofing plan complete (26 workstreams, 7 buckets).

### v0.47.0 — Impact Tool (original)

Original impact tool release. Superseded by v0.52.0.

### v0.21.0 — ChromaDB-free retrieval

The opt-in `turbovec` backend can now **embed *and* search with zero ChromaDB**: Google Research's **TurboQuant** compressed index (8–16× smaller vectors) plus a bundled `OnnxMiniLMEmbedder` that produces vectors **byte-identical** to ChromaDB's (`all-MiniLM-L6-v2`; verified cosine 1.0). Retrieval stays at/above parity (fact recall 0.744 → 0.800). Enable with `backend: turbovec` in `neuralmind-backend.yaml` — see the [ChromaDB-free local](https://github.com/dfrostar/neuralmind/blob/main/docs/use-cases/chromadb-free-local.md) walkthrough. This retires the dependency behind the recurring **CVE-2026-45829** advisory; flipping the default is the staged next step. Full details: [v0.21.0 release notes](https://github.com/dfrostar/neuralmind/blob/main/docs/releases/RELEASE_NOTES_v0.21.0.md).

### v0.20.0 — Measure the onboarding lift

`neuralmind eval --onboarding` turns NeuralMind's differentiator into a number: does an agent that inherits a **committed team memory** retrieve better on its *first* queries than a cold agent? The headline is the **top-k module hit-rate lift** (run-dependent: **+0.9 to +11.6 points** observed across runs on the reference fixture, and trending toward the low end of that band as the cold-path baseline itself improves, leaving less headroom for the memory layer to add), with fact-recall + grounding as honest secondaries; budget-neutral, gated in CI at lift ≥ 0. Full details: [v0.20.0 release notes](https://github.com/dfrostar/neuralmind/blob/main/docs/releases/RELEASE_NOTES_v0.20.0.md).

> 📊 New: a single **[Benchmarks & Results](Benchmarks)** page collects every measured, CI-gated number (token reduction, faithfulness delta, synapse and onboarding lift, pts, ChromaDB-free parity) with reproduction commands.

### v0.14.0 — Measure faithfulness

`neuralmind eval` turns "does the memory make answers *better*, not just shorter?" into a number: it scores whether NeuralMind's selected context contains more of the facts a correct answer needs than a matched-budget naive baseline (a **faithfulness delta**), plus grounding and contradiction checks. 100% local by default (`--json` and `--selfcheck` too); the LLM-as-judge is opt-in. It's a contributor/CI quality gate — run it from a **source checkout** (the `evals/` gold set isn't bundled in the pip wheel; from an installed wheel the command points you at the repo). The first release where you can measure *answer quality*, not just token reduction. Full details: [v0.14.0 release notes](https://github.com/dfrostar/neuralmind/blob/main/docs/releases/RELEASE_NOTES_v0.14.0.md).

### v0.13.0 — Measurement foundation

The scaffolding to *prove* the memory helps, not just claim it: a 100%-local **faithfulness eval** (a versioned query + gold-fact dataset and an offline expected-fact-recall scorer), **polyglot retrieval fixtures (TypeScript + Go)** so quality is measured beyond Python, and a written documentation process. No runtime change to your install — this is the fitness function the eval-first roadmap (v0.13→v0.16) builds on. The full `neuralmind eval` report is the next increment. Full details: [v0.13.0 release notes](https://github.com/dfrostar/neuralmind/blob/main/docs/releases/RELEASE_NOTES_v0.13.0.md).

### v0.12.0 — Install Doctor

`neuralmind doctor` inspects an install (code graph, semantic index, synapse memory, MCP server, Claude Code hooks, query memory) and reports each piece with a status and the exact fix; `--json` for agents, non-zero exit to gate CI. Full details: [v0.12.0 release notes](https://github.com/dfrostar/neuralmind/blob/main/docs/releases/RELEASE_NOTES_v0.12.0.md).

### v0.11.0 — Directional Synapses

The synapse layer now learns *what comes next*, not just *what goes together*: a `synapse_transitions` table, a `next_likely()` API, the `neuralmind next` CLI, and the `neuralmind_next_likely` MCP tool. Full details: [v0.11.0 release notes](https://github.com/dfrostar/neuralmind/blob/main/docs/releases/RELEASE_NOTES_v0.11.0.md).

### v0.10.0 — Agent Ergonomics

A content-aware PostToolUse compression footer (categorized line counts + repeated-line detection) and `neuralmind last` to recover dropped middle output without re-running the command. Full details: [v0.10.0 release notes](https://github.com/dfrostar/neuralmind/blob/main/docs/releases/RELEASE_NOTES_v0.10.0.md).

### v0.9.0 — Enterprise-Ready

Phase 3 of the release arc. Every tagged release now auto-publishes a multi-platform container image to GHCR (`ghcr.io/dfrostar/neuralmind:vX.Y.Z` and `:latest`, `linux/amd64` + `linux/arm64`) and attaches a CycloneDX JSON SBOM to the GitHub Release. New [`docs/use-cases/air-gapped.md`](https://github.com/dfrostar/neuralmind/blob/main/docs/use-cases/air-gapped.md) walkthrough covers the strictest deployment posture — no outbound network at install, build, runtime, or query. New [`docs/COMPLIANCE-SUMMARY.md`](https://github.com/dfrostar/neuralmind/blob/main/docs/COMPLIANCE-SUMMARY.md) consolidates NIST AI RMF + SOC 2 + GDPR claims previously scattered across `SECURITY-GUIDE.md` and the now-extracted enterprise docs, with a "how to verify yourself" command for every claim.

No production code changes — pure CI + docs. Full details: [v0.9.0 release notes](https://github.com/dfrostar/neuralmind/blob/main/docs/releases/RELEASE_NOTES_v0.9.0.md).

### v0.8.0 — Always-On

`neuralmind watch` and `neuralmind serve` are first-class production processes now. Committed [systemd](https://github.com/dfrostar/neuralmind/blob/main/scripts/systemd/) and [launchd](https://github.com/dfrostar/neuralmind/blob/main/scripts/launchd/) templates, plus a Windows Task Scheduler walkthrough in the [Scheduling Guide](Scheduling-Guide#always-on-neuralmind-watch--neuralmind-serve-v08), keep both running across reboots and crashes. `neuralmind serve` exposes a `/healthz` endpoint (unauthenticated, returns `{"status":"ok","version":"…"}`) for Docker `HEALTHCHECK` and systemd `ExecStartPost` probes. Cross-platform walkthrough at [`docs/use-cases/always-on.md`](https://github.com/dfrostar/neuralmind/blob/main/docs/use-cases/always-on.md).

Distribution (v0.7.0) made NeuralMind reachable. Always-on (v0.8.0) makes it persistent — the synapse store accumulates 24/7 whether you're at the keyboard or not. Full details: [v0.8.0 release notes](https://github.com/dfrostar/neuralmind/blob/main/docs/releases/RELEASE_NOTES_v0.8.0.md).

### v0.7.0 — Install anywhere

NeuralMind now installs five ways: `pip`, `pipx`, `uv`, Docker, and source. Same package, same CLI, same MCP server, same graph view — every path. The Quick Start matrix lives at the top of the [Installation](Installation) page and the [README](https://github.com/dfrostar/neuralmind/blob/main/README.md#install--pick-your-path); the repo's root [`Dockerfile`](https://github.com/dfrostar/neuralmind/blob/main/Dockerfile) is multi-stage, non-root, and pre-wheels every transitive dep so the runtime image doesn't need a C toolchain. PyPI keywords got a long-overdue refresh too, so search ranking for `graph-view`, `hebbian-learning`, and friends finally matches the v0.6.0 product copy.

Also in v0.7.0: a P2 fix in the JSONL bridge (rotation race that could drop events under logrotate/copytruncate) and a test-coverage gap on `/api/queries`. Full details: [v0.7.0 release notes](https://github.com/dfrostar/neuralmind/blob/main/docs/releases/RELEASE_NOTES_v0.7.0.md) · [Install paths walkthrough](https://github.com/dfrostar/neuralmind/blob/main/docs/use-cases/install-paths.md).

### v0.6.0 — Graph view + live activity feed

`neuralmind serve` now streams synapse + file events to the canvas in
real time over SSE. Affected nodes pulse as the brain works; a
sidebar log keeps the most recent ~80 events. A cross-process JSONL
bridge means a separate `neuralmind watch` daemon, a Claude Code
session, or any other process feeds the same live feed via
`<project>/.neuralmind/events.jsonl`. Pin UX (visible glyph,
Pin/Unpin button, Unpin-all), Cmd/Ctrl-K quick-switch, a 1–3-hop
depth slider, replay-last-query overlay, edge tooltips, and a
min-weight synapse slider round out the release.

The pitch flipped: v0.5.4 made the brain inspectable; v0.6.0 makes
it legible. You can sit there and **watch the hippocampus learn
your codebase, live**.

Multi-tool unlock: every agent (Claude Code, Cursor, OpenClaw,
Hermes-Agent) talking to the same project reinforces the same
synapse store, and the v0.6.0 canvas now shows the **union** of
their activity. See [docs/use-cases/multi-agent.md](https://github.com/dfrostar/neuralmind/blob/main/docs/use-cases/multi-agent.md).

Full details: [v0.6.0 release notes](https://github.com/dfrostar/neuralmind/blob/main/docs/releases/RELEASE_NOTES_v0.6.0.md) ·
[Architecture: event bus + JSONL bridge](Architecture#event-bus-and-jsonl-bridge-v06) ·
[CLI Reference: `neuralmind serve`](CLI-Reference#serve)

### v0.5.4 — Graph view foundation

The Obsidian-style force-directed graph that v0.6.0 made live first
shipped in v0.5.4. Code nodes coloured by community; structural edges
and Hebbian synapses drawn together; backlinks, synaptic neighbours,
semantic quick-switch, and one-click open-in-editor. Per-session
access token bound to 127.0.0.1 by default (since v0.46.2 the token
persists across restarts). Builds on v0.5.0's bundled MCP server.

### v0.4.0 — Brain-like synapse layer

NeuralMind runs as a second brain alongside the LLM: a persistent
SQLite-backed weighted graph that learns associations between code
nodes from co-activation, decays unused edges, and answers via
spreading activation. Includes the `neuralmind watch` daemon, three
Claude Code lifecycle hooks (SessionStart, UserPromptSubmit,
PreCompact), and a memory exporter that surfaces learned
associations to Claude Code's auto-memory system. See the
[release notes](https://github.com/dfrostar/neuralmind/blob/main/docs/releases/RELEASE_NOTES_v0.4.0.md) or the
[Architecture](Architecture#synapse-layer-v04) and [Learning Guide](Learning-Guide#v04-synapse-layer)
sections.

## Quick Links

### Start here

| Page | When to read it |
|------|-----------------|
| **[Setup Guide](Setup-Guide)** | First-time setup for Claude Code, Cursor, Claude Desktop, or any MCP client |
| **[Use Cases](Use-Cases)** | Step-by-step walkthroughs by persona: Claude Code user, cost optimization, any-LLM, offline/regulated, growing monorepo |
| **[Comparisons](Comparisons)** | Honest "NeuralMind vs X" pages: Cursor, Copilot, Cody, Aider, Claude Projects, LangChain, long context, prompt caching, RAG, tree-sitter |
|| **[Tier2-Operator-Guide](Tier2-Operator-Guide.md)** | Team tier commands, honest scope, troubleshooting |
|| **[Multi-Project-Scoping](Multi-Project-Scoping.md)** | Working across multiple codebases — isolation rules for NeuralMind, memU, and agent memory |
|| **[Upgrade-Guide](Upgrade-Guide.md)** | Free → Team flow, downgrade, troubleshooting |
|| **[Billing-Runbook](Billing-Runbook.md)** | Operator: quote → invoice → issue → renew, the manual Team sales path |
| **[Compatibility Matrix](../COMPATIBILITY.md)** | Version compatibility, Python support, known issues, upgrade paths |
| **[Benchmarks & Results](Benchmarks)** | Every measured, CI-gated number — token reduction, faithfulness delta, synapse and onboarding lift, ChromaDB-free parity — with reproduction commands |

### Enterprise & Deployment

| Page | For... |
|------|--------|
| **[Deployment Guide](../DEPLOYMENT-GUIDE.md)** | DevOps/Infrastructure: what runs and what it opens, pip and container installs, hardening, health checks, audit log, backup, team rollout |
| **[Security Guide](../SECURITY-GUIDE.md)** | Security teams: access control, encryption, secrets management, NIST AI RMF, SOC 2, threat models |
| **[Upgrading Guide](../UPGRADING.md)** | Everyone: How to upgrade between versions, breaking changes, rollback procedures |

### Reference

| Page | Contents |
|------|----------|
| [Installation](Installation) | `pip` / `pipx` / `uv` / Docker / source — pick your path (v0.7.0) |
| [Usage Guide](Usage-Guide) | End-to-end examples for every command |
| [CLI Reference](CLI-Reference) | All CLI commands, flags, and output shapes |
| [API Reference](API-Reference) | Python API (`NeuralMind`, `ContextResult`, `TokenBudget`) |
| [Architecture](Architecture) | How the 4-layer progressive disclosure system works — incl. the embedding-model spec + index inspection/debugging reference |
| [Limits & Failure Modes](Limits-and-Failure-Modes) | Where it stops working: when one query isn't enough, the repo-size envelope, and the per-language support matrix |
| [Integration Guide](Integration-Guide) | MCP, CI/CD, VS Code, JetBrains, any-LLM piping |
| [Scheduling Guide](Scheduling-Guide) | Automate audits with Windows Task Scheduler, GitHub Actions, or cron |
| [Learning Guide](Learning-Guide) | Opt-in memory + the brain-like synapse layer that learns associations from how you use the codebase (Hebbian co-activation with decay), the single learning system since v0.25.0 |
| [Brain-Like Learning](https://github.com/dfrostar/neuralmind/blob/main/docs/brain_like_learning.md) | Design rationale for the v0.3.x learning system |
| [v0.4.0 Release Notes](https://github.com/dfrostar/neuralmind/blob/main/docs/releases/RELEASE_NOTES_v0.4.0.md) | Brain-like synapse layer: continuous co-activation, spreading activation, lifecycle hooks |
| [Troubleshooting](Troubleshooting) | Common issues and fixes |
| [FAQ](FAQ) | 30+ frequently asked questions answered |

## What is NeuralMind?

Token-efficient retrieval plus persistent memory for AI coding agents.

- **Retrieval.** A 4-layer progressive-disclosure index surfaces ~800 tokens of structured context for any code question, instead of loading 50,000+ tokens of raw source.
- **Memory.** A synapse layer learns which code goes together from how you work, and Claude Code gets it at session start and with each prompt; since v4.9.0, Hermes-Agent gets it with each turn too, through `neuralmind install-hermes-plugin`.

Measured effect: **45–246× fewer retrieval tokens than pasting every source file** on the [public benchmark](https://github.com/dfrostar/neuralmind/blob/main/docs/benchmarks/public.md), at 95% mean gold-file recall; on private repos `neuralmind benchmark .` reported 12–50× against its fixed 50K-token baseline before v4.5.0, which now divides by the measured size of the repo instead; 5.1× on the tiny CI fixture at v4.3.4 (CI fails below 4.0×). Works offline after the first build; model-agnostic.

NeuralMind doesn't compress tool output. Its PostToolUse hooks used to hand Claude compressed copies of `Bash` and `Grep` output, but Claude Code adds a hook's context next to the tool result rather than replacing it, so the copies cost tokens instead of saving them ([compression benchmark](https://github.com/dfrostar/neuralmind/blob/main/docs/benchmarks/compression.md)). The hooks now inject nothing.

### The core problem

```
You: "How does authentication work in my codebase?"

❌ Traditional: Load entire codebase → 50,000 tokens → $0.15-$3.75/query
✅ NeuralMind: Smart context → ~800 tokens → $0.002-$0.06/query
```

### When do I reach for it?

Short answer: if any of these describe you, start with the [Use Cases](Use-Cases) page.

- My Claude Code session hits context limits mid-task
- My monthly LLM bill is climbing
- I start every session re-pasting project structure
- The agent reads a 2,000-line file to answer one question
- I want to query my codebase from ChatGPT / Gemini / a local model
- I need AI coding help but code can't leave my machine

Full symptom-and-goal matrix in the main [README](https://github.com/dfrostar/neuralmind/blob/main/README.md#-when-do-i-reach-for-neuralmind).

## Quick Start

```bash
# Install
pip install neuralmind

# Setup
cd your-project
neuralmind build .

# Use
neuralmind wakeup .
neuralmind query . "How does authentication work?"
neuralmind skeleton src/auth/handlers.py
```

Claude Code users, install the lifecycle hooks (session memory, a recap of the
previous session on a fresh start, prompt-time recall, the stale-decision guard,
and a Bash output cache for `neuralmind last`):

```bash
neuralmind install-hooks .
neuralmind init-hook .        # auto-rebuild on every git commit (optional)
neuralmind watch &            # always-on synapse learning from file edits (optional)
```

Hermes-Agent users, install the plugin (related files and decisions in every
turn, and the recap on a session's first turn):

```bash
neuralmind install-hermes-plugin .
```

The plugin goes into a Hermes home: `--hermes-home`, else the one plain `hermes`
uses (the active Hermes profile, if `hermes profile use` selected one, else
`$HERMES_HOME`, else `~/.hermes`; `%LOCALAPPDATA%\hermes` on Windows). The path pins that project for
every Hermes session in that home, and sessions in other repositories then also
put their edited files' paths into its synapse store, from where
`neuralmind memory publish` can carry them into the committed team-memory
bundle. If you use Hermes across several projects, install without a path, and
the plugin follows the directory Hermes works in (the terminal CLI's, or a
standalone gateway's); in Hermes Desktop, ACP editor sessions and per-session
workspaces, pin a project or set `NEURALMIND_PROJECT`.

## Compare to alternatives

| Compared against | Short verdict |
|---|---|
| [Cursor `@codebase`](Comparisons#cursor-codebase) | Works only in Cursor; NeuralMind works anywhere |
| [GitHub Copilot](Comparisons#github-copilot) | Copilot is hosted completions; NeuralMind is local context |
| [Claude Projects](Comparisons#claude-projects) | Projects reload all files every turn; NeuralMind retrieves only what the query needs |
| [Long context windows](Comparisons#long-context) | Possible ≠ cheap — NeuralMind drops per-query cost ~60× |
| [Prompt caching](Comparisons#prompt-caching) | Caching amortizes big prompts; NeuralMind makes them small |

Full list: [Comparisons](Comparisons).

## Prove it on your code

Don't trust fixture numbers — measure it on your own repo:

```bash
pip install neuralmind
neuralmind build .
neuralmind benchmark . --contribute
```

This outputs your reduction ratio, tokens per query, and an estimated monthly savings figure at Claude 3.5 Sonnet pricing. The `--contribute` flag produces a ready-to-share JSON blob you can paste into a PR (or a [benchmark submission issue](https://github.com/dfrostar/neuralmind/issues/new?template=community-benchmark.yml)) to add to the public leaderboard.

Full walkthrough: [Does NeuralMind work on *your* codebase?](https://github.com/dfrostar/neuralmind/blob/main/docs/use-cases/benchmark-your-repo.md)

## Support

- [GitHub Issues](https://github.com/dfrostar/neuralmind/issues) — bug reports, feature requests
- [GitHub Discussions](https://github.com/dfrostar/neuralmind/discussions) — questions and ideas
- [Main README](https://github.com/dfrostar/neuralmind/blob/main/README.md) — always the most current overview
