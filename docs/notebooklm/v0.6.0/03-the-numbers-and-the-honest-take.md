# The numbers, the day-in-the-life, and the honest take

*Mixed-register source for the NotebookLM video. Combines a
developer-experience walkthrough with the measurable claims and a
short skeptic's section. Use as the "is this real, and is it worth
it" arc.*

---

## A day in the life

You sit down to add a feature to a project you don't fully
remember. You have Claude Code open in one terminal. You install
NeuralMind once, with `pip install neuralmind graphifyy` and a
quick `graphify update . && neuralmind build .` against your
project. Five minutes, one time.

You ask Claude Code a question. Behind the scenes, the
`SessionStart` hook fires and your agent gets about four hundred
tokens of project orientation: the project name, the
architecture summary, the top code clusters. That replaces the
agent's usual session-start ritual of reading half your repo to
get its bearings. The `UserPromptSubmit` hook fires next and
injects a few hundred more tokens of synapse-recall context — the
nodes the brain has learned tend to fire together when you ask
this kind of question.

You hit enter. Your agent answers in about a thousand tokens of
input context instead of fifty thousand. Same question, same
answer, fifty times less money. If you're a Claude 3.5 Sonnet user
running a hundred questions a day, that's the difference between
fifteen dollars a day and twenty-five cents. Across a month, it's
the difference between four hundred fifty dollars and seven
dollars.

Now you pop a second terminal and run `neuralmind serve`. A
browser tab opens to your codebase as an Obsidian-style
force-directed graph — nodes colored by community, structural
edges in one shade, learned synapses in another. You ask Claude
Code another question. The nodes the agent looked at *pulse* on
the canvas. You can see, in real time, which clusters of code the
agent considered. If it picked the wrong cluster, you know
immediately — not from logs, from a visual.

You save a file in your editor. The corresponding node pulses.
The file watcher coalesced your edit into a co-activation event,
which reinforced the synapse edges to all the other files you
recently touched, which fired a `synapse` event, which the live
feed picked up, which the browser rendered. End-to-end latency:
under a second.

You ask another question and watch the brain work. Over the next
week, the pulses concentrate around the parts of the codebase you
actually live in. The hub nodes get stronger. The dead corners
fade. You're not maintaining this. You're just using your editor
and your agent normally. The brain learns from the use.

That's the day in the life. Two terminals, one extra browser tab,
two existing tools talking through a shared associative memory.

## The numbers, as honestly as we can state them

The headline is forty to seventy times per-query token reduction.
That number measures one specific thing: how many tokens of input
context the agent receives when it queries through NeuralMind,
versus how many it would receive if you loaded the relevant raw
source instead. It's measured on real codebases. The bundled
fixture in CI shows about six times because the fixture is
deliberately tiny — about five hundred lines, sized to catch
regressions, not to look impressive. Real-world submissions from
two outside repos show forty-six and sixty-six times. Your
number, when you run `neuralmind benchmark .` on your own code,
will land in that range if you have a real codebase. Small repos
land lower; large repos with rich call graphs land higher.

That's the retrieval-side number. It's the one we lead with
because it's the one that's literally measured every commit in
continuous integration, and the one anyone can reproduce in
thirty seconds with `bash scripts/demo.sh` on a fresh clone.

But there's a second number you should know, and the honest
assessment doc spells it out: the *end-to-end* cost reduction on
a typical agent workload is three to ten times, not forty to
seventy. The retrieval stage is one cost line item among several
in a real session. The agent still spends tokens on its own
thinking, on tool output, on conversation history. NeuralMind
drops one big slice of the pie. It doesn't drop the whole pie.

We say this out loud because we want you to install NeuralMind
only if it actually helps you. If you're spending fifty dollars
a month on LLM calls against a small repo, three to ten times is
nice but not life-changing. If you're spending five hundred or
five thousand a month, three to ten times is the difference
between a budget conversation and a non-issue. The honest
assessment doc has the math.

The graph view doesn't change the numbers. It changes whether
you trust them. When you watch a node pulse the instant you save
a file, and the next pulse is your agent picking up that node in
its very next query, the abstraction stops being abstract. You
can see the system doing what it claims.

## When NeuralMind isn't worth installing

There's a short list, written down in `docs/HONEST-ASSESSMENT.md`,
of cases where you should skip this:

Small codebases under about five thousand tokens, where you can
just paste the whole thing into the context window. NeuralMind's
setup time exceeds its benefit there.

Workflows where you don't pay per token — local-only LLMs with
flat-rate compute, or hobby projects where cost doesn't matter.
The retrieval-quality benefit still exists, but the headline pitch
is cost reduction, and there's nothing to reduce.

Use cases that aren't code questions. NeuralMind is specialized.
It indexes a call graph from `graphify-out/graph.json`. It does
not help with documentation QA, customer-support ticket triage,
or any other non-code agent task.

Cases where you only want inline completions. Use Copilot or your
editor's native completion. NeuralMind is the context layer, not
the completion layer; the two coexist but they're solving
different problems.

You almost certainly *do* want NeuralMind if your monthly LLM
spend has crossed the point where a few hours of setup pays back
in days, if you run an AI coding agent against a real codebase
(ten thousand lines or more), or if you've been frustrated that
your agent does the same thing wrong over and over because it
keeps "forgetting" your codebase between sessions.

## The two competing pitches, side by side

For people who care about cost: NeuralMind reduces per-query
retrieval cost forty to seventy times, end-to-end cost three to
ten times, measured on every commit in CI, reproducible in thirty
seconds on a fresh clone. Pay-per-query at Claude 3.5 Sonnet rates
drops from roughly fifteen cents to roughly two-tenths of a cent.
A hundred queries a day, four hundred fifty a month becomes
seven. Multiplied across a team, the math gets unmissable.

For people who care about quality and trust: NeuralMind is an
associative memory layer for your AI coding agent. It learns from
how you and the agent actually use the codebase — co-activations
reinforce edges, unused edges decay, spreading activation
surfaces related code on every prompt. Version 0.6.0 makes that
learning *visible*. The graph view pulses in real time as the
brain works. When retrieval feels wrong, you can replay the last
query on the canvas and see exactly which nodes the agent got. If
you've ever wondered "is my AI tool actually using the right
context," 0.6.0 is the first version where that's a two-second
visual answer.

The two pitches aren't in tension. They're the same product
viewed through two lenses. The cost reduction is what justifies
the install on a spreadsheet. The graph view is what makes the
install land *emotionally* — what flips you from "I should try
this" to "I want to show this to everyone on my team."

## What to do next

The install is `pip install neuralmind graphifyy`. The verification
is `bash scripts/demo.sh` on a fresh clone. The graph view is
`neuralmind serve` after `neuralmind build .`. The benchmark on
your own code is `neuralmind benchmark . --contribute`, which
also produces a paste-ready JSON blob you can submit to the public
leaderboard if you want.

If after thirty seconds the demo numbers don't look meaningful for
your workflow, `pip uninstall neuralmind` and the cost is the
five minutes. If they do, the next step is the actual install on
your real repo and a week of using it. The graph view's job is to
make sure that week is the most interesting week of agent usage
you've had in months.

That's the offer. It's open source, MIT licensed, runs entirely on
your machine, no cloud, no telemetry, no signup. Try it or don't.
We'll be over here, watching the canvas pulse.
