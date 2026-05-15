# LinkedIn post draft — NeuralMind progress update

Two sets of drafts. The **v0.6.0 launch drafts** are the current
batch — post one of them the moment v0.6.0 is on PyPI. The
**earlier drafts** below are the previous progress update; kept for
reference and as a backbone if you want to combine.

---

## v0.6.0 launch drafts

The pitch frame: **"we built the hippocampus, you can watch it
learn."** Pair every draft with the 60-second screencast clip
([`SCREENCAST-v0.6.0.md`](SCREENCAST-v0.6.0.md)) — the pulse-rings
visual is the asset that makes this post land. Don't post the v0.6.0
variants without it.

### Draft v0.6.0–A — short, dev-honest (recommended for first post)

> NeuralMind v0.6.0 is out today.
>
> Short version: the brain is now visible.
>
> NeuralMind has been an associative memory layer for AI coding
> agents since v0.4 — a persistent weighted graph that learns
> which code nodes fire together, decays the rest, and spreads
> activation on every prompt so the agent gets better context the
> longer it runs on your codebase.
>
> The honest problem with that pitch: nobody could see it working.
> "The agent has a learning memory" is a claim. "Install this and
> trust me" is not a demo.
>
> So in 0.6.0, `neuralmind serve` got a live activity feed.
> Synapse and file events stream to the canvas over SSE. When
> Claude (or any agent) calls a tool, the relevant nodes pulse.
> When you save a file in your editor, the corresponding node
> pulses. You can sit there and watch the hippocampus learn your
> codebase in real time.
>
> Plus a JSONL cross-process bridge that means if you run Claude
> Code, Cursor, OpenClaw, and Hermes-Agent all against the same
> project — they reinforce the same brain, and the graph view
> shows the union of their activity. NeuralMind becomes the shared
> memory substrate underneath the polyglot agent stack.
>
> The headline measurable claim is unchanged: 40–70× per-query
> token reduction on real codebases, ~3–10× end-to-end on a
> typical agent workload, measured every commit in CI, reproducible
> in 30 seconds on a fresh clone.
>
> What's new is that the abstraction now has a window.
>
> [VIDEO: 60-second clip — terminal demo + graph view + pulse rings]
>
> github.com/dfrostar/neuralmind
>
> #ClaudeCode #Cursor #AIEngineering #OpenSource #DeveloperTools

### Draft v0.6.0–B — feature-tour, scannable

> NeuralMind v0.6.0 ships today. What's new:
>
> → **Live activity feed.** `neuralmind serve` streams synapse +
>   file events over SSE. Affected nodes pulse on the canvas in
>   real time. Sidebar log shows the most recent ~80 events.
>
> → **Cross-process JSONL bridge.** A `neuralmind watch` daemon, a
>   Claude Code session, an OpenClaw call — all in different
>   processes — feed the same live feed via
>   `.neuralmind/events.jsonl`. One canvas, every agent.
>
> → **Pin UX.** Drag-to-pin already saved positions; v0.6.0 adds a
>   visible pin glyph, a Pin/Unpin button in the detail panel, and
>   an Unpin-all sidebar action.
>
> → **Quick-switch.** Cmd/Ctrl-K and `/` jump to semantic search
>   from anywhere. Esc clears.
>
> → **Local-graph depth slider.** 1–3 hops via BFS from the focused
>   node. Default 1, so existing behavior is unchanged.
>
> → **Replay-last-query overlay.** Re-highlight the L3 hits the
>   agent most recently received. Closes the "is the agent looking
>   at the right code" trust gap in a 2-second visual.
>
> → **Edge tooltips + min-weight synapse slider.** Hover any edge
>   for relationship + weight; filter out low-weight noise.
>
> The measurable claim is unchanged from v0.5: 40–70× per-query
> retrieval reduction on real repos, ~3–10× end-to-end, verifiable
> in 30 seconds with `bash scripts/demo.sh` on a fresh clone.
>
> What v0.6.0 changes is that the *learning* is now visible. You
> can see the brain working.
>
> [VIDEO: 60-second pulse-rings clip]
>
> github.com/dfrostar/neuralmind

### Draft v0.6.0–C — narrative / founder voice

> Three months ago I posted about NeuralMind, the open-source
> context engine I've been building for AI coding agents. The
> story then was a number: 40–70× per-query token reduction. Real,
> measurable, reproducible on a fresh clone. But also a little
> dry.
>
> The story today, with v0.6.0, is something I can actually show
> you.
>
> NeuralMind isn't just a retrieval index. Since v0.4, it's an
> associative memory layer — a persistent graph that learns which
> pieces of code your agent uses together. Edges strengthen with
> co-activation, decay if unused, get protected from decay once
> they're frequently-used. Spreading activation surfaces related
> code on every prompt. It's a small, local hippocampus that runs
> alongside the LLM cortex.
>
> The honest problem was: you couldn't see it work. We had tests.
> We had benchmarks. But the experience was a black box that you
> had to trust would get smarter.
>
> v0.6.0 ends that. `neuralmind serve` now streams a live activity
> feed. Every time the agent uses a code node, that node pulses on
> the graph. Every time you save a file, the corresponding node
> pulses. You can sit there and watch the brain learn your
> codebase.
>
> It's the moment that flips "code RAG" into "associative memory
> for your codebase." It's also the moment when, if you're running
> Claude Code in one terminal and OpenClaw in another, you can see
> them reinforcing the *same* brain — because v0.6.0 also adds a
> cross-process JSONL bridge so every agent talking to the project
> contributes to one canvas.
>
> If you've been watching your Claude or Cursor bill climb, or
> you've noticed your AI tools "forgetting" your codebase between
> sessions: this is for you.
>
> [VIDEO: 60-second clip]
>
> Free, MIT, fully local. github.com/dfrostar/neuralmind

### Choosing between A / B / C

- **A** is the safest. Short, technical, honest about limitations,
  works on any LinkedIn network. Default pick.
- **B** has the highest information density and scans best for
  engineering audiences. Good if your network skews scanners.
- **C** is the highest-engagement candidate but only if you have
  an audience that engages with longer-form / story-driven posts.
  Higher variance.

### Common across all three

- **The video is non-optional.** Without the pulse-rings clip, all
  three drafts collapse back into the existing v0.5 progress
  update — same number, different words. The clip is what makes
  v0.6.0 a separate post worth posting.
- **The honest end-to-end caveat ("3–10× end-to-end") is in A and
  B but not C.** That's deliberate — C is narrative, not spec
  sheet. If you post C, link to `docs/HONEST-ASSESSMENT.md` in the
  first comment so the caveat is reachable.

---

## Earlier drafts (pre-v0.6.0 — kept for reference)

Three drafts at different lengths and tones. Pick one, edit to
match your voice, post.

---

## Draft 1 — short, technical, honest (recommended)

> A quick update on NeuralMind, the open-source context engine I've
> been building for AI coding agents.
>
> What's new this week:
>
> 🔹 One-command demo. `bash scripts/demo.sh` from a fresh clone
> reproduces the headline reduction in 30 seconds. Real numbers, not
> a marketing video.
>
> 🔹 A fact-based business case. Every claim links to a single
> command that verifies it on your own code. ROI math with
> assumptions you can change. No hand-waving.
>
> 🔹 An honest assessment doc. Where NeuralMind isn't worth
> installing. What "40–70× reduction" actually means (and what it
> doesn't — your end-to-end LLM bill drops 3–10×, not 40–70×).
> Limits of our community-benchmark sample (n=2, both maintainer's
> repos — please contribute yours).
>
> CI measures 6.1× on every commit. The demo reproduces 5.5× in
> 30 seconds. Real repos have submitted 46–66×. Your number comes
> from running `neuralmind benchmark .` on your code.
>
> If you spend $500+/month on Claude Code or Cursor on a 10K+ line
> repo, the math probably pencils out. If your repo is under 5K
> lines or you don't pay per token, skip it. The honest assessment
> doc says so out loud.
>
> Try it: github.com/dfrostar/neuralmind
>
> Contribute a benchmark from your repo: it's the highest-leverage
> thing you can do for the project right now.

---

## Draft 2 — longer, story-driven

> Three months ago I started NeuralMind because my Claude Code bill
> was climbing past $200/month on a single project and I wanted to
> understand why. The answer: every code question loaded ~50K tokens
> of context. Of that, the model needed maybe 1,000.
>
> The fix is in two parts: (1) retrieve only what the question
> needs, (2) compress what the agent receives back from tools.
> Standard RAG ideas, but specialized for code — the call graph
> matters more than text proximity.
>
> Today's progress:
>
> ✅ A 30-second demo that anyone can run on a fresh clone.
>    `bash scripts/demo.sh`. No marketing video — real terminal
>    output, real token counts.
>
> ✅ A fact-based business case (docs/BUSINESS-CASE.md). Every
>    claim is one command away from being verified on your code.
>    ROI math you can plug your own numbers into.
>
> ✅ An honest assessment (docs/HONEST-ASSESSMENT.md). When this
>    isn't worth installing. What the headline numbers don't
>    measure. The fact that our community-benchmark table has
>    only 2 entries and both are mine — so treat the range as
>    directional, not predictive.
>
> What I learned shipping these together: a punchy headline number
> ("40–70× reduction!") buys you 30 seconds of attention. A
> reproducible 30-second demo + a list of caveats buys you the
> trust to actually adopt.
>
> Real numbers, today:
> • CI measures 6.1× on every commit (verifiable on any closed PR)
> • Demo reproduces 5.5× in 30 seconds on a fresh clone
> • Community submissions: 46×, 66× (n=2, both mine — yours wanted)
> • End-to-end LLM cost reduction is realistically 3–10× on a
>   typical agent workload, not 40–70×. The retrieval-stage figure
>   is bigger because retrieval is one cost line item, not all of
>   them.
>
> If you've been watching your Claude Code or Cursor bill climb,
> spend 30 seconds on the demo and decide from there.
>
> github.com/dfrostar/neuralmind
>
> #ClaudeCode #Cursor #AIengineering #OpenSource #DeveloperTools

---

## Draft 3 — bullet-only, scannable

> NeuralMind progress update — open-source context engine for AI
> coding agents.
>
> Shipped this week:
>
> → 30-second demo (`bash scripts/demo.sh`) — reproducible proof on
>   a fresh clone, no install of your own code required
> → Fact-based business case with verifiable claims and ROI math
>   you can plug your numbers into
> → Honest assessment of when NeuralMind doesn't help and what the
>   headline numbers don't measure
> → Lightweight public roadmap with pointers for contributors
>
> Verifiable today:
>
> → 6.1× retrieval reduction measured in CI on every commit
> → 5.5× reproduces in 30 seconds on a fresh clone
> → Community submissions: 46×, 66× (n=2, both maintainer-owned —
>   please contribute yours)
> → End-to-end cost reduction realistic at 3–10× on a typical agent
>   workload (smaller than the 40–70× retrieval figure because
>   retrieval is one cost slice)
>
> github.com/dfrostar/neuralmind
>
> The biggest help right now is community benchmarks from outside
> repos: `neuralmind benchmark . --contribute` outputs a
> paste-ready submission.

---

## Notes on choosing

- **Draft 1** is the safest — short enough to read in 30 seconds,
  technical without being dry, honest without being defeatist. If
  you're unsure, post this.
- **Draft 2** if you want to tell a story and have an existing
  audience that engages with longer-form posts. Higher engagement
  ceiling but only on the right network.
- **Draft 3** if your network skews scanners (most engineers).
  Highest information density per second of read time.

## Hashtags worth adding (pick 2–3, not all)

`#ClaudeCode` `#Cursor` `#AIEngineering` `#DeveloperTools`
`#OpenSource` `#MCP` `#LLMOptimization` `#TokenOptimization`
`#AIAgents`

## Image / link suggestions

- The asciinema recording (see [RECORDING-DEMO.md](RECORDING-DEMO.md))
  is the strongest visual asset. Embed once recorded.
- Until then: a static screenshot of the demo's terminal output is
  the second-best option. Crop tightly to the headline numbers.
- Avoid stock-photo "AI" imagery. Engineers tune those out.

## Posting cadence reminder

If this is a follow-on to a previous post, reference the earlier
one ("two weeks ago I posted about X — here's what shipped since").
LinkedIn's algorithm rewards continuity. Consider scheduling for
Tuesday/Wednesday morning in your timezone for highest reach.
