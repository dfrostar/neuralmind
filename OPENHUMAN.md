# NeuralMind ↔ OpenHuman — how to think about it

> A concept/positioning note, not a spec. It frames the relationship between
> NeuralMind and [OpenHuman](https://github.com/tinyhumansai/openhuman)
> (`tinyhumansai/openhuman`, ~31k★, GPL-3 — *"Your Personal AI super
> intelligence. Private, Simple and extremely powerful."*) and proposes where we
> go from here.

## TL;DR

OpenHuman and NeuralMind are **the same bet, scoped to different domains.** Both
are local-first, privacy-preserving, brain-metaphor memory systems that compress
context aggressively and learn over time so an agent boots with earned context
instead of a cold window. The difference is breadth vs. depth: **OpenHuman is the
brain for your whole life** (mail, calendar, docs, chats, repos); **NeuralMind is
the brain for your codebase.** They are not competitors. OpenHuman's traction is
the clearest market validation NeuralMind has that its core thesis is right — and
OpenHuman's skills registry is a concrete place NeuralMind can plug in as the
deep code-memory specialist.

## What OpenHuman is (grounding, from its own README + skills repo)

- **A personal AI for your whole life.** Local-first, private, ships as a Tauri
  desktop app; "from install to a working agent in a few clicks."
- **Memory engine ("Neocortex") built on Memory Trees** — ≤3k-token Markdown
  chunks, scored and folded into hierarchical summary trees in SQLite, plus a
  human-editable Obsidian wiki. Memory here is *summarization / hierarchy* based,
  inspired by Karpathy's obsidian-wiki workflow.
- **TokenJuice** — a token-compression layer over every tool call, scrape, email
  body and search payload before the model reads it (~80% reduction).
- **118+ integrations** (Gmail, Notion, GitHub, Slack…) via Composio one-click
  OAuth, auto-fetching into the memory tree on a ~20-minute loop.
- **A skills registry** ([`openhuman-skills`](https://github.com/tinyhumansai/openhuman-skills)):
  a skill declares `manifest.json` (id/version/description/auth/platforms),
  exposes **tools** the agent can call (each returns a JSON string), and
  implements **lifecycle hooks** (`init`/`start`/`stop`, cron). Skills run in a
  sandboxed **QuickJS** runtime (synchronous, no async/await) with bridge APIs for
  SQLite, HTTP, scheduling, notifications, and optional local model inference.

## The two systems, side by side

| Dimension | OpenHuman | NeuralMind |
|---|---|---|
| **Domain** | Your whole life — mail, calendar, docs, chats, repos | Your codebase |
| **Memory model** | Memory Trees: hierarchical summaries (a **tree**) | Hebbian synapse layer: weighted associations + spreading activation (a **graph**) |
| **Brain metaphor** | "Neocortex" | Hippocampus + associative cortex (agent = stateless cortex) |
| **Compression** | TokenJuice (~80% off tool output) | Progressive disclosure L0–L3 (38–85× vs. pasting files) |
| **Learning signal** | Sync + summarize on a 20-min loop | Co-activation (Hebbian), edge decay, directional "what you edit next" |
| **Primary surface** | Tauri desktop app + skills registry | MCP tools + Claude Code hooks + file watcher |
| **Distribution** | 118+ Composio integrations | git-committed, reviewable team-memory bundles |
| **Stack** | Node 24+, Rust, Tauri, TypeScript skills (QuickJS) | Python, tree-sitter, ChromaDB, SQLite |
| **License** | GPL-3 | MIT |

The convergence is striking and independent: same brain framing, same
local-first stance, same "compress before the model reads it" reflex, same
"memory persists so the agent starts warm" promise — arrived at separately.

## Three mental models for the relationship

1. **Convergent validation.** A 31k★ project betting on local-first, private,
   compressed, brain-like agent memory is the strongest external signal that
   NeuralMind's foundational thesis is where the market is heading. It de-risks the
   vision. We are not alone or early-and-wrong; we are early-and-right, in a lane
   nobody else has gone *deep* on.

2. **Depth vs. breadth.** OpenHuman is the *horizontal* life brain — it knows a
   little about everything you touch. NeuralMind is the *vertical* code brain — it
   knows your repository the way a senior engineer would: what files go together,
   what you edit next, what patterns matter. **NeuralMind is to code what
   OpenHuman is to life.** A horizontal assistant's general memory of a repo will
   never match a specialist that parses it with tree-sitter across ten languages
   and learns its associations.

3. **Tree vs. graph memory.** These are genuinely *different memory primitives*,
   not two takes on one. OpenHuman's Memory Trees are **summarization +
   hierarchy** (roll detail up into ever-coarser summaries). NeuralMind's synapse
   layer is **association** (weighted edges between nodes, strengthened by
   co-use, decayed by neglect, recalled by spreading activation). A tree answers
   "what is the gist of this corpus?"; a graph answers "given I just touched X,
   what else lights up?" The honest read is that a complete agent memory wants
   both — which is exactly why integration is interesting rather than redundant.

## Where NeuralMind is differentiated

- **Associative recall, not just summarization** — the Hebbian synapse layer
  (`neuralmind/synapses.py`) learns co-edited/co-activated nodes and decays stale
  ones; spreading activation surfaces "what usually comes next." Measured to lift
  top-k retrieval hit-rate +11.7 pts, budget-neutral.
- **Real code structure** — built-in tree-sitter backend across **ten languages**
  (Python, TypeScript, Go, Rust, Java, C, C++, C#, Ruby, PHP), with typed
  `inherits` / `imports_from` / call edges. Not generic document chunking.
- **Agent-neutral and MCP-native** — one learned map serves Claude Code, Cursor,
  Cline, Continue; no desktop app required, no vendor lock-in.
- **Reproducible evals** — public benchmark on real OSS repos (100% gold-file
  recall, MRR 0.96), committed traces, CI-gated. Claims you can re-run.
- **git-portable team intuition** — memory commits as reviewable bundles and is
  inherited on `git clone`; knowledge travels with the repo, not a cloud account.

The repo's existing one-liner already says it: *the agent "learns your codebase
the way a senior engineer would."* That is the lane to own.

## Strategic options

### 1. NeuralMind as an OpenHuman skill *(lead with this)*

OpenHuman's skill contract — `manifest.json` + tools that return JSON +
`init`/`start`/`stop` lifecycle hooks — maps cleanly onto NeuralMind's existing
MCP tool surface (`neuralmind/mcp_server.py`). Shipping NeuralMind as an
`openhuman-skills` entry would make it **the deep code-memory brain inside
OpenHuman**: when an OpenHuman user is working on code, NeuralMind answers the
"where does this live / what goes with it / what changes next" questions that a
general Memory Tree of a repo can't. OpenHuman gets best-in-class code recall for
free; NeuralMind gets distribution into a 31k★ user base.

*Constraints to investigate before committing engineering:*
- **Runtime bridge.** Skills run in a synchronous **QuickJS** sandbox, while
  NeuralMind is a Python process (ChromaDB + SQLite + tree-sitter). The skill
  would be a thin TS shim that proxies to a local NeuralMind process/CLI over the
  skill's HTTP/subprocess bridge, not a port. Validate that the sandbox permits
  this (local HTTP to `neuralmind serve`, or subprocess to the CLI).
- **License interplay.** NeuralMind is **MIT**, OpenHuman is **GPL-3**. MIT code
  is fine to depend on from a GPL-3 project, but distributing a combined work has
  GPL implications — keep NeuralMind a separately-licensed, separately-installed
  local service the skill *talks to*, rather than bundling its source into the
  GPL tree. Confirm with the actual skill packaging model.

### 2. Architecture cross-pollination

- *Borrow inward:* evaluate hierarchical-summary trees (OpenHuman's Memory Tree
  shape) as a model for rolling NeuralMind's L0→L3 disclosure layers up into
  coarser repo-level summaries.
- *Offer outward:* associative graph recall (decay + spreading activation) is a
  primitive OpenHuman's tree-only memory lacks — a candidate contribution or
  shared idea.

### 3. Positioning hygiene

Say "the code-memory specialist" out loud, consistently, so NeuralMind reads as
**complementary** to OpenHuman, not a smaller derivative of it. The brain-metaphor
overlap is an asset (shared mental model the market is being taught) *if* we own a
clearly distinct organ: OpenHuman is the neocortex of your life; NeuralMind is the
hippocampus of your codebase.

## Recommendation & open questions

**Recommendation:** pursue Option 1 (NeuralMind as an OpenHuman skill) as the
flagship move, with Option 3 (positioning) applied immediately and Option 2 as
ongoing R&D. The integration is high-leverage (distribution + a real capability
gap filled) and low-architecture-risk *if* the bridge is a proxy, not a port.

**Open questions to resolve first:**
1. Does the QuickJS skill sandbox allow a skill to reach a local NeuralMind
   process (HTTP to `neuralmind serve`, or CLI subprocess)? If not, integration
   needs a different shape.
2. Does the GPL-3 / MIT boundary stay clean under OpenHuman's skill packaging
   (separately-installed local service vs. bundled source)?
3. Is the right wedge a *single* "ask the codebase" tool, or the full progressive
   L0–L3 + synapse recall surface exposed as several skill tools?

---

*References: this note is grounded in NeuralMind's own `CLAUDE.md` (the
cortex / hippocampus framing) and `README.md` positioning, and in OpenHuman's
public [README](https://github.com/tinyhumansai/openhuman) and
[skills registry](https://github.com/tinyhumansai/openhuman-skills).*
