# NeuralMind ↔ Tri-Node Memory — how to think about it

> A concept/positioning note, not a spec. It frames the relationship between
> NeuralMind and [Tri-Node Memory](https://github.com/CorbanMonoxide/Tri-Node-Memory)
> (`CorbanMonoxide/Tri-Node-Memory`, early-stage, MIT — *"A memory architecture
> for AI agents… persistent, correctable memory without letting it trample your
> data."*), and names the feature gap the comparison exposes.

## TL;DR

Tri-Node Memory is a **governance convention**, not a memory engine — a
directory layout plus a write policy. Its entire pitch is the human/agent
trust boundary, stated in one sentence: *"Agent reads your vault. Agent
writes to its journal. Never the other way."* That is the clearest public
articulation yet of a principle NeuralMind already **enforces mechanically**
but has never **said out loud**. The project is tiny (single-digit stars, a
handful of commits) and poses no competitive pressure; its value to us is as
a second independent validation — after [OpenHuman](OPENHUMAN.md) — that the
market is converging on trust-separated agent memory, and as a prompt to (1)
state our own write policy that crisply, and (2) ship the **promotion
protocol** that neither project has: the agent *proposing* learned memory
into the human-trusted layer as a reviewable diff.

## What Tri-Node Memory is (grounding, from its own README)

- **Three nodes, defined by who may write them:**
  1. **Human Vault** — your personal knowledge base (an Obsidian vault of
     markdown). *Read-only to the agent.*
  2. **Agent Journal** — the agent's own persistent memory. *Agent
     read/write.*
  3. **Inference Layer** — scratch space for in-flight work, so ephemera
     pollutes neither vault.
- **Separation is the product.** Agents consume the vault but cannot modify
  it; when an agent wants an insight captured in the vault, the human
  explicitly authorizes that write, per instance.
- **Plain files, separate git repos.** No database, no server, no retrieval
  engine. Each node is markdown under git, so audit and revert come free.
- **Harness-agnostic via bootstrap files.** Integration is a `CLAUDE.md` /
  `CODE.md` that states the rules when a session starts — it works with any
  agent that reads project instructions (Claude Code, Codex, OpenClaw), and
  the same fact means the boundary is enforced by *instruction*, not by
  mechanism.

## The two systems, side by side

| Dimension | Tri-Node Memory | NeuralMind |
|---|---|---|
| **What it is** | A governance convention (layout + write policy) | A memory engine (graph, learning, compression) |
| **Domain** | General knowledge/notes memory | Your codebase |
| **Memory model** | Markdown files in three git repos | Code graph + Hebbian synapse layer with decay and spreading activation |
| **Trust boundary** | Human vault read-only to agent — stated as policy in a bootstrap file | Hooks never write human-curated files; agent learning is confined to the synapse store; the shared layer only changes via a provenance-stamped, MAX-merged, git-committed bundle published explicitly (`team_memory.py`) |
| **Enforcement** | Honor system (the agent is told the rule) | Mechanical (the write paths don't exist) |
| **Retrieval** | Agent greps/reads raw markdown | Progressive disclosure L0–L3 + associative recall |
| **Learning signal** | Only what the agent writes down | Co-activation (Hebbian), edge decay, directional "what you edit next" |
| **Human-side UI** | Obsidian — humans curate where they already work | `CLAUDE.md` / docs + exported `SYNAPSE_MEMORY.md` |
| **Stack** | Markdown + git (+ optionally Obsidian) | Python, tree-sitter, ChromaDB, SQLite |
| **License** | MIT | MIT |

## Three mental models for the relationship

1. **Convergent validation, again.** OpenHuman validated local-first,
   brain-like, compressed agent memory at 31k★ scale. Tri-Node validates a
   *different axis from the small end*: someone chose human/agent **vault
   separation as their entire pitch**, and it resonated enough to travel.
   Most memory projects (Mem0, Letta, context-vault, agentmemory) mix
   human-authored and agent-inferred entries in one store; the "whose memory
   is this and can I trust it" problem is becoming legible enough to market
   on. NeuralMind bet on that separation early — this is evidence the bet
   reads.

2. **Policy vs. mechanism.** Tri-Node states the rule; NeuralMind enforces
   it. A bootstrap file asking the agent not to write the vault is a polite
   request — nothing stops a confused or prompt-injected agent from doing it
   anyway. NeuralMind's equivalent boundary is structural: agent learning
   lands in the synapse store (`personal` / `branch:*` namespaces), decays
   when stale, and can only reach the team-trusted layer through a separate,
   git-committed bundle that must be published explicitly — reviewable like
   any diff — where MAX-merge means a bundle can only *raise* weights it
   asserts and never touches the developer's personal layer. Separation-with-provenance is also the defensible answer
   to memory poisoning: a single agent-writable store that the agent also
   trusts on read is a prompt-injection persistence mechanism.

3. **Governance layer vs. engine layer.** These aren't competitors; they're
   different layers of the same stack. Tri-Node has governance and no engine
   — no retrieval (raw-markdown recall burns tokens and won't scale past a
   few hundred notes; that's precisely the failure progressive disclosure
   exists for), no ranking, no decay, no learning. NeuralMind has the engine
   and, until now, an *unstated* governance story buried in module
   docstrings. The complete product wants both, said plainly.

## What Tri-Node does better (borrow inward)

- **The one-sentence write policy.** *"Agent reads your vault. Agent writes
  to its journal. Never the other way."* NeuralMind's equivalent — **"agents
  learn in their own store; the human and team layers change only through an
  explicit, git-committed bundle — never the agent writing them directly"** —
  belongs in the README and docs at exactly that bluntness, not implied
  across `team_memory.py` and `synapse_memory.py` docstrings.
- **A named home for ephemera.** The Inference Layer gives scratch output
  somewhere to go so it contaminates neither trusted layer. NeuralMind's
  branch namespaces (`branch:<name>`) play a similar role for feature-branch
  learning; worth describing in those terms.
- **Meeting humans where they curate.** Obsidian as the human-side surface
  is a good instinct. NeuralMind's markdown export (`SYNAPSE_MEMORY.md`,
  Claude auto-memory) is the same move in the other direction — agent memory
  rendered human-readable — and should be framed as the two-way bridge it is.

## The gap neither ships: the promotion protocol

Tri-Node's per-write "agent asks, human authorizes" ritual is the manual
version of something no memory project ships as a first-class workflow:

> The agent **proposes** a high-confidence learned memory into the
> human-trusted layer **as a reviewable diff**; a human ratifies it in
> review; only then is it trusted.

NeuralMind is unusually close to this. The pieces exist: synapse weights
with an LTP threshold (confidence), `publish_team_memory` (export),
provenance stamping, MAX-merge semantics (a proposal can only add, never
silently rewrite), and a git-committed bundle that already lives in version
control as a reviewable diff. What's missing is the *proposing* — a
`neuralmind propose` (or
PreCompact/session-end hook) that notices associations crossing the
threshold and opens the bundle diff for human ratification, rather than
waiting for someone to run publish by hand. Per the roadmap's own
discipline, its onboarding/recall lift should be measured by the v0.13 eval
harness before the design locks, and it sequences naturally with the v0.16
portable cross-agent memory format and the team-memory arc
([#175](https://github.com/dfrostar/neuralmind/issues/175)).

## Recommendation

1. **Positioning hygiene (shipped alongside this note):** state the write
   policy in one sentence in `README.md` and the wiki, and name the three
   layers we already have — human-curated (read-only to agents),
   agent-learned (decaying synapse store), team-shared (explicit,
   git-committed bundle). We independently built the stronger version of Tri-Node's
   headline; say so plainly, and credit the convergence where it's visible.
   Done in the same PR as this note: README "Who writes what — the memory
   trust boundary" section + Security & Compliance bullet, and the wiki
   Learning-Guide's "Write policy" section.
2. **Feature (measured, then shipped):** the promotion protocol above —
   agent-proposed, human-ratified memory promotion as a reviewable diff —
   gated on the v0.13 harness, aligned with #175 and the v0.16 portable
   format.
3. **No competitive response needed.** Watch the project; if the vault-
   separation framing keeps traveling, that's confirmation the positioning
   in (1) is the right lane.

---

*References: this note is grounded in NeuralMind's own `CLAUDE.md`,
`neuralmind/team_memory.py`, `neuralmind/namespaces.py`, and
`neuralmind/synapse_memory.py`, in Tri-Node Memory's public
[README](https://github.com/CorbanMonoxide/Tri-Node-Memory), and in the
companion positioning note [`OPENHUMAN.md`](OPENHUMAN.md).*
