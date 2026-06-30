# Reddit seed kit

Copy-paste-ready Reddit posts and comments to **honestly seed real threads**
about NeuralMind — the threads that later become the rows in
[`../community/reddit-roundup.html`](../community/reddit-roundup.html). No
threads can be summarized until threads exist; this is how they come to exist
without faking anything.

**One hard rule (same as the rest of [`./README.md`](README.md)): disclosed-maker
only.** Every post here is first person, as the author. No personas, no
sockpuppets, no "unaffiliated user" framing, no upvote-asking. If a subreddit
won't allow a disclosed maker to post, we don't post there — we don't post in
disguise. The benchmark's credibility is the whole point; astroturfing throws
it away.

These three moves map to the honest-seeding playbook:

1. **Genuine question, not a promo** → Post 1.
2. **Answer support questions as the maintainer, with code** → Comment templates.
3. **AMA after a major release** → Post 2.

---

## Subreddit rules cheat-sheet (read before posting)

| Subreddit | Self-promo tolerance | Best fit | Notes |
|---|---|---|---|
| `r/LocalLLaMA` | Technical maker posts OK if local-first + honest | Launch post, benchmark question | Already have [`r-localllama.md`](r-localllama.md). Lead with "100% local, no API key". |
| `r/ClaudeAI` | OK if genuinely about Claude Code | Hooks/memory angle, AMA | Most receptive to the lifecycle-hook seam. |
| `r/ChatGPTCoding` | OK if useful, low-promo | Agent-context question, support answers | Practitioner crowd; show, don't sell. |
| `r/selfhosted` | OK if privacy/local angle leads | Privacy/local-first | Frame as "nothing leaves the machine". |
| `r/programming` | **Strict — no self-promo posts** | *Comments only*, on existing threads | Never submit your own project here. Use the warm-up comment style from [`hn-warmup-comments.md`](hn-warmup-comments.md), adapted. |
| `r/MachineLearning` | **Strict** | Benchmark methodology discussion only | High bar; only the benchmark-design question, heavily technical. |

**Universal:** check each sub's rules + flair requirements the day you post
(they change). Many require a "self-promotion ratio" — comment genuinely in the
sub for a while before you post your own thing.

---

## Post 1 — Genuine question (the honest opener)

**Where:** `r/LocalLLaMA` or `r/ChatGPTCoding`. This is a *real question* you
actually want answers to — the disclosure is honest, but the post earns its
place by being useful even if nobody clicks the repo.

### Title

```
Benchmarking AST/symbol-graph context vs full-file paste vs vector RAG for coding agents — what oracle are you using for "did it retrieve the right code"?
```

### Body (copy-paste)

```
I've been benchmarking how coding agents get code into context — full-file
paste vs a symbol/call-graph assembly vs plain vector RAG — and I keep hitting
the same methodology wall I want this sub's take on: how do you score "did the
retrieval actually surface the right code" without an LLM-as-judge?

The approach I settled on, and where I'm unsure:

- Gold file = the objective definition site of a named symbol in the query.
- A method "answered" iff that file lands in the assembled context.
- Verifiable with one `rg` command, deterministic, no judge.

What it catches well: keyword search (ripgrep) misses the right file ~29% of
the time on the repos I tested (requests, click), because it has no notion of
meaning. What I'm unsure about: this rewards *findability* but says nothing
about whether the surrounding context is enough to *answer* — a same-encoder
vector RAG ties on findability and is cheaper on tokens, but dumps chunks
instead of structured context. Is there a cheap, judge-free way to score
"answerability", not just "located"?

Disclosure: this came out of building an open local memory layer
(github.com/dfrostar/neuralmind) — the harness is in the repo, so I'm not
asking you to trust my numbers, I'm asking whether the oracle design is sound.
Genuinely want to hear how others are scoring code retrieval, especially anyone
who's tried answerability oracles that don't need a frontier model in the loop.
```

**Why this works:** it's a real open problem (answerability oracle), it discloses
in-line, and the one link is incidental to the question. People answer questions;
they downvote ads. The resulting thread — whatever the verdict — is honest
material for the roundup's "what devs discuss" section.

---

## Post 2 — Post-release AMA

**Where:** `r/ClaudeAI` (best) or `r/LocalLLaMA`. Post within a day or two of a
release that has a concrete, defensible headline. Don't run an AMA on a quiet week.

### Title

```
I built NeuralMind, an open-source local memory + code-retrieval layer for AI coding agents (just shipped v0.41). AMA — especially the skeptical benchmark questions.
```

### Body (copy-paste — fill the bracketed bits at post time)

```
Maker here, posting with full disclosure. NeuralMind is an open-source, 100%
local layer that gives AI coding agents (Claude Code, Cursor, Cline, any MCP
client) persistent memory of your codebase + on-demand structured context, so
the agent reads ~800 tokens for a code question instead of 50k+.

Just shipped v0.41 [→ one concrete sentence on what the release added]. Rather
than list features, here's the honest state of it so the AMA starts from truth:

What's real and reproducible:
- 100% gold-file recall at 38–85× fewer tokens vs pasting files, on pinned real
  OSS repos. Run it: `python -m evals.public.run`.
- Beats the incumbent codebase-memory-mcp on retrieval ranking, MRR 0.96 vs
  0.23, same repos/scorer.

What I'll say plainly so you don't have to drag it out of me:
- "40–70×" is a retrieval-token reduction, NOT a 40–70× bill cut. Realistic
  end-to-end is ~3–10× because output + history are unchanged.
- A well-tuned vector RAG ties me on pure findability and is cheaper on raw
  tokens. The extra tokens buy assembled context to *answer*, not just locate.
- Language depth is uneven — strongest on Python/TS; C/C++ macros & templates
  aren't fully modeled; dynamic-language call edges are best-effort.
- The public benchmark table is still small (mostly my repos). Outside numbers
  are the thing I most want.

Ask me anything — benchmark design, the Hebbian synapse learning, the Claude
Code hook seam (PreCompact/PostToolUse), where it's weak, why you maybe
shouldn't bother (small repos / free tier / already on prompt caching).

Repo: github.com/dfrostar/neuralmind
Benchmark methodology + raw data: github.com/dfrostar/neuralmind/blob/main/docs/benchmarks/public.md
```

**AMA conduct:** be present for the first 3–4 hours. Answer the hostile
questions *first* and *fully* — that's what earns the thread credibility (and
makes it quotable in the roundup's criticism section). Never delete a critical
comment.

---

## Comment templates — answering support/questions as the maintainer

Drop these only where they genuinely answer the thread. Lead with substance;
disclose the moment NeuralMind is named; one link max. Adapt the opening line to
what the OP actually asked — a generic paste reads as spam.

### Template A — "how do I cut my Claude/Cursor token bill on a big repo?"

```
A few things that helped before reaching for any specific tool:
1. Don't paste files — give the agent a map first (symbols + call edges) and let
   it pull only the bodies it needs. The recall hit is smaller than you'd think
   if retrieval is decent.
2. Compress tool output before it hits the window. Read/Bash/Grep results are
   often 90% boilerplate the model never needed.
3. Persist what the agent already "understood" so it isn't re-derived every turn.

Set expectations honestly though: most of these cut *retrieval* tokens, not your
whole bill — output and conversation history dominate a long session, so think
~3–10× end-to-end, not the 40–70× you'll see in retrieval-only benchmarks.

(Disclosure: I build an open MCP server around exactly this,
github.com/dfrostar/neuralmind — but the three points above are tool-agnostic
and worth doing by hand.)
```

### Template B — "is it just RAG / how is this different from vector search?"

```
The retrieval core *is* a local vector index — no point hiding that. Two things
sit on top: (1) progressive disclosure that assembles structured context
(map → symbols → call edges) instead of dumping top-k chunks, and (2) a synapse
layer that learns which files go together from your actual usage and decays
unused links. In my own benchmark the `embedding-rag` baseline is literally my
encoder in isolation, so the gap between it and the full system is exactly what
that assembly layer costs and buys — measured, not asserted. And on bare
findability, that vector baseline ties the full system and is cheaper on tokens;
I report that, it's not buried.

(Disclosure: this is from building github.com/dfrostar/neuralmind; harness is in
the repo if you want to tear the methodology apart.)
```

### Template C — "does it work with Claude Code / Cursor / Cline?"

```
Yes — it ships an MCP server plus Claude Code lifecycle hooks. `neuralmind
install-mcp` auto-detects and registers with Claude Code, Cursor, Cline, and
Claude Desktop; any MCP client or plain CLI works too. The Claude Code hook seam
(SessionStart / PreCompact / PostToolUse) is the underused part — PreCompact in
particular lets you persist a distilled memory before the window gets summarized
away, so recall happens whether or not the model thinks to ask.

(Disclosure: I maintain it — github.com/dfrostar/neuralmind — but the hook seam
is just Claude Code's public lifecycle API and worth using with any setup.)
```

---

## After posting — feed the flywheel

For every real thread these produce (yours or others'):

1. Add a row to the "Live Reddit threads" table in
   [`../community/reddit-roundup.html`](../community/reddit-roundup.html) with
   the real permalink, title, and score read off the page that day.
2. If a comment makes a quotable point (praise *or* criticism), add it as a
   linked `<blockquote>` in the matching section — real quote, real `u/handle`,
   real permalink. Never paraphrase into quotation marks.
3. If it's a `vs <tool>` thread, also add it to that comparison page's
   "What developers say on Reddit" section.
4. Once ≥3 real threads exist, run the publish checklist in
   [`../community/README.md`](../community/README.md).
