# Session handoff — Tri-Node positioning + write-policy thread

**Last updated:** 2026-07-13 · **State:** PR #311 merged to `main`
(commit `89d8b39`). This thread is *done except for two optional
follow-ups* — a Reddit reply the maker posts personally, and a deferred
feature. Nothing is blocked on code.

---

## What prompted this thread

A Reddit post surfaced [Tri-Node Memory](https://github.com/CorbanMonoxide/Tri-Node-Memory)
(`CorbanMonoxide/Tri-Node-Memory`, MIT, early-stage) — an agent-memory
project whose entire pitch is human/agent **vault separation**:
*"Agent reads your vault. Agent writes to its journal. Never the other
way."* It's a governance convention (markdown + git, no engine), not a
competitor. The interesting part: it states the trust boundary more
crisply than NeuralMind ever did, even though NeuralMind *enforces* the
stronger version mechanically.

## What shipped (merged, PR #311)

- **`TRINODE.md`** — positioning note in the `OPENHUMAN.md` vein:
  governance-convention vs engine, second independent validation (after
  OpenHuman) of trust-separated memory, side-by-side table, and the
  **promotion-protocol gap** neither project ships.
- **`README.md`** — "Who writes what — the memory trust boundary"
  section + a "Trust-Separated Memory" Security & Compliance bullet.
- **`docs/wiki/Learning-Guide.md`** — a "Write policy" section under
  Privacy & Data.
- **Copilot review correction** (worth remembering): the docs originally
  said the team layer changes "only through a PR a human merges." That
  **overstates** what's enforced. What `neuralmind/team_memory.py`
  actually guarantees is: agent learning writes only to `synapses.db`
  (`personal`/`branch:*`), never the human/team files; promotion requires
  an **explicit publish to a separate, git-committed bundle**
  (`.neuralmind-team-memory.json`, MAX-merged, provenance-stamped, decays).
  Human PR review is what git *enables*, not what the code *mandates*
  (CI/direct commits can also write the bundle). All docs now say
  "explicit, git-committed, reviewable bundle." Keep future wording scoped
  to that when touching team-memory claims.

## ▶ Next session — do this if/when we pick it up

1. **Post the Reddit reply (maker posts as themselves).** The maker owns
   NeuralMind (`dfrostar`), so this is disclosed self-promo — Reddit
   punishes the *undisclosed* kind. Two drafts below; both are written to
   be worth reading with the link removed. Post the long one unless the
   subreddit skews terse. **Don'ts:** no benchmark/"40–70×" numbers in the
   comment (flips peer→marketer); don't reply again downthread unless the
   author engages first.

   <details><summary>Long version</summary>

   > This is great — *"Agent reads your vault. Agent writes to its journal.
   > Never the other way"* is the clearest one-sentence statement of the
   > human/agent trust boundary I've seen anywhere. Most memory projects mix
   > human-authored and agent-inferred entries in one store, and then you can
   > never tell whether a "memory" is something you asserted or something the
   > agent hallucinated three sessions ago and kept compounding. Making the
   > separation the *headline* is the right call, and separate git repos
   > giving you audit/revert for free is a nice touch.
   >
   > Closest thing I've seen from the code side is
   > [NeuralMind](https://github.com/dfrostar/neuralmind) (MIT) — same
   > boundary, enforced mechanically instead of by instruction: the agent's
   > learned layer is a decaying synapse store, and the only path from "agent
   > learned it" to "team trusts it" is an explicit, git-committed bundle.
   > Worth a look if you haven't seen it — the two designs rhyme hard,
   > arrived at independently.
   >
   > The gap I don't think anyone ships yet is the **promotion protocol**: the
   > agent *proposing* a high-confidence memory into the human vault as a
   > reviewable diff, instead of asking permission ad hoc. Your per-write
   > authorization ritual is the manual version of it. If you formalize that,
   > I think it's the feature.
   >
   > One thing you may hit as vaults grow: raw markdown recall gets
   > token-expensive fast once the agent has to grep and read whole files.
   > Progressive disclosure (summaries first, drill down on demand) fixes that
   > and would port to a file-based design.
   >
   > Starred — curious where the inference layer goes.

   </details>

   <details><summary>Short version</summary>

   > Love this — "agent reads your vault, agent writes to its journal, never
   > the other way" is the crispest statement of the human/agent trust
   > boundary I've seen. [NeuralMind](https://github.com/dfrostar/neuralmind)
   > converged on the same separation from the code side — agent learning
   > lives in its own decaying store and only reaches the human/team layer
   > through an explicit, git-committed bundle. Two projects arriving at the
   > same boundary independently usually means it's the right boundary. The
   > thing neither ships yet: the agent *proposing* memories into the human
   > vault as reviewable diffs. That's the feature. Starred.

   </details>

2. **(Deferred feature) The promotion protocol** — `TRINODE.md`
   Recommendation 2, intentionally not built yet. Agent *proposes* a
   high-confidence learned association into the team bundle **as a
   reviewable diff**; human ratifies in review; only then is it trusted.
   Pieces already exist: synapse LTP threshold (confidence),
   `publish_team_memory` (export), provenance stamp, MAX-merge, the
   committed bundle. **Missing:** the *proposing* — e.g. a
   `neuralmind propose` command or a PreCompact/session-end hook that
   notices threshold-crossing associations and opens the bundle diff.
   Per roadmap discipline: **measure onboarding/recall lift on the v0.13
   eval harness before locking the design**; sequence with issue
   [#175](https://github.com/dfrostar/neuralmind/issues/175) (team memory)
   and the v0.16 portable cross-agent memory format. If built, it ships as
   a `feat:` with the full docs+SEO checklist (see `CLAUDE.md`).

## Pointers

- Merged note: `TRINODE.md` · companion: `OPENHUMAN.md`
- Enforcement source of truth: `neuralmind/team_memory.py`,
  `neuralmind/namespaces.py`, `neuralmind/synapse_memory.py`
- The other, broader launch handoff: `docs/launch/NEXT-SESSION.md`
