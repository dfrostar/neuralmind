# NeuralMind v0.43.0 — the codebase remembers *why*, not just *what*

NeuralMind has always indexed what a codebase **is** — its nodes, edges, and
learned associations. It never indexed **why** it is that way. So every time an
agent asked "why is `resolveOrgId` per-handler instead of middleware?", the
answer — "avoids Prisma on `/health`, `/metrics`, `/token`; keeps tests simple" —
lived in a human's head or a scrolled-past chat, never in any artifact the graph
could recall. The next agent re-derives it, re-asks, or worse, silently undoes
the decision.

v0.43.0 makes rationale a first-class, recallable memory.

## What's in this release

| Change | What | Surface |
|--------|------|---------|
| **Decision provenance** | rationale captured from a `Decision:` git trailer becomes a subject-keyed memory | `neuralmind why <query>` |
| **Prompt-time recall** *(default on)* | matching decisions injected on `UserPromptSubmit` alongside synapse recall | `NEURALMIND_PROVENANCE_INJECT` |
| **Zero new storage** | git history *is* the store — the trailer is the persistence, nothing to build or drift | — |

## Why this release matters

Every other NeuralMind memory is *derived* — embeddings from code, synapse
weights from co-activation. Provenance is the one memory only a human can author,
and it was the one thing the graph couldn't hold. Capturing it at the cheapest
possible point — a trailer on the commit that makes the change — means the *why*
travels with the *what*, forever, in the one artifact that never gets lost: git
history itself. No database, no schema, nothing to keep in sync. Adopt the
trailer today and it works retroactively on every commit you've already made.

## How it works

Add a `Decision:` trailer to a commit message. Optionally list the symbols it
concerns (backticked symbols in the rationale are picked up automatically):

```
cli: resolve org id per handler

Decision: resolveOrgId is per-handler, not middleware — avoids Prisma on
          /health, /metrics, /token; keeps tests simple.
Subjects: `resolveOrgId`, `authMiddleware`
```

Then ask, from the terminal or through your agent:

```
$ neuralmind why "why is resolveOrgId per-handler?"

## NeuralMind decision provenance

- `resolveOrgId`, `authMiddleware`: resolveOrgId is per-handler, not middleware —
  avoids Prisma on /health, /metrics, /token; keeps tests simple. (see commit ba25fed)
```

Recall is subject-keyed: a decision surfaces only when its symbols appear in the
query (or, at prompt time, in the agent's prompt), so it stays quiet until it's
relevant.

## What the agent actually sees post-install

| Agent | What changes | How to use it |
|-------|--------------|---------------|
| **Claude Code** | On `UserPromptSubmit`, when a prompt mentions a symbol with a recorded decision, the rationale is injected as context (alongside synapse recall) | Just ask about the symbol; the *why* arrives with it — no tool call |
| **Cursor / Cline** | Same injection via the shared hook runtime | Same — provider-agnostic |
| **Generic MCP / CLI** | `neuralmind why <query>` returns the recorded rationale with its commit SHA | Call it directly, or wire it into a pre-edit check |
| **Any human** | `neuralmind why "<question>"` answers from git history | Onboard to a decision without asking whoever made it |

## Configuration

| Env var | Default | Effect |
|---------|---------|--------|
| `NEURALMIND_PROVENANCE_INJECT` | `1` (on) | `0` → skip decision injection in the `UserPromptSubmit` hook. Fails open regardless; a provenance miss never disrupts the prompt. |

## Honest scope

- Provenance is **only as good as the trailers you write** — this captures
  rationale, it does not infer it. No trailer, no memory.
- Recall matching is lexical over subjects (explicit `Subjects:` + backticked
  symbols in the rationale), not semantic. Name the symbols you mean.
- Harvest reads recent git history (default last 300 commits); very old
  decisions beyond that window aren't surfaced.
- Git history is the store, so a decision is as durable — and as rewritable — as
  the commit that carries it.

## Upgrade

```
pip install --upgrade neuralmind
```

Nothing to rebuild. Start adding `Decision:` trailers; `neuralmind why` reads
them from history immediately. Injection is on by default and fails open — set
`NEURALMIND_PROVENANCE_INJECT=0` to opt out.

> **Note:** cohesion outlier detection (`NEURALMIND_SYNAPSE_OUTLIERS`) and
> `neuralmind gaps` — the other two "Surface what you can't see" features — ship
> in **v0.44.0**, not this release. See `RELEASE_NOTES_v0.44.0.md`.
