# LinkedIn post draft — NeuralMind progress update

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
