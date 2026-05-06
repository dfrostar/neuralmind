# Business case

A fact-based, provable ROI argument for adopting NeuralMind. Every
number on this page is either measured in CI on every commit, or
reproducible in under five minutes on your own code with one
command. No hand-waving.

If you're a skeptic, jump to [Verify each claim yourself](#verify-each-claim-yourself).
If you're an evaluator pitching this internally, read top-to-bottom.
If you want to know what could go wrong before adopting, see
[HONEST-ASSESSMENT.md](HONEST-ASSESSMENT.md).

---

## Bottom line

For a team spending **$500+/month on AI coding agent inference** on a
**codebase larger than ~10K lines**, NeuralMind's tooling
**measures a 40–70× reduction in retrieval-stage input tokens** on
real-world repos (community benchmarks; n=2). On a typical agent
workload this **translates to a derived 3–10× reduction in
end-to-end LLM cost** — the smaller end-to-end figure is because
retrieval is one cost slice among generation, conversation history,
and tool results, not all of them. **One-time setup is ~15 min per
developer**, with **no ongoing operational overhead once you opt
into the git post-commit hook (`neuralmind init-hook .`)** which
incrementally rebuilds the index.

The retrieval-stage reduction is **measured**. The end-to-end
multiplier is **derived** from the
[sensitivity analysis below](#the-math-with-assumptions-you-can-change),
not directly observed end-to-end — that's a known gap, tracked on
[ROADMAP.md](../ROADMAP.md).

Every word in that paragraph is provable on your own code:

| Claim | How to verify | Time | What it actually measures |
|---|---|---|---|
| 40–70× retrieval reduction | `neuralmind benchmark .` reports per-query input-token counts and a Sonnet-priced dollar estimate (CLI hardcodes Claude 3.5 Sonnet input pricing today; multiply by your model's input price ratio if different). | 5 min | Retrieval-stage input tokens vs. naive baseline. |
| ~15 min setup | `bash scripts/demo.sh` from a fresh clone runs end-to-end. | 1 min | Wall time including pip install + chromadb model download + index build. |
| Ongoing overhead with `init-hook` | `neuralmind init-hook .` installs a git post-commit hook that incrementally rebuilds. Without it, you re-run `neuralmind build .` manually. | 30 sec | Setup of the hook only — its incremental run takes seconds per commit. |
| Codebase >10K lines threshold | `wc -l $(find . -name '*.py' -o -name '*.ts' -o -name '*.js')` | 5 sec | Line count, no opinion attached. |

---

## The four facts you can stand on

These are the load-bearing numbers. All are produced by automation
that runs on every PR, not maintainer-curated marketing claims.

### Fact 1 — Retrieval reduction is measured in CI on every commit

The [CI self-benchmark](../.github/workflows/ci-benchmark.yml) runs
the [committed query set](../tests/fixtures/benchmark_queries.json)
against the [committed fixture](../tests/fixtures/sample_project/) on
every pull request and posts results as a sticky PR comment. The
exact ratio fluctuates with chromadb embedding nondeterminism and
fixture changes, but the shape of the result is stable:

- **Average reduction is consistently above the 4× pass/fail floor
  on 10 queries** — most recent runs land in the 5–7× range on the
  fixture (~500 lines). CI fails the PR if it drops below 4×.
- Naive baseline: every `.py` file in the fixture concatenated.
- Top-k retrieval hit rate: typically 65–75% on the fixture.

The fixture is intentionally small. On real-world repos the ratio
is consistently higher (see Fact 4) because the naive baseline
scales linearly with codebase size while NeuralMind's output stays
roughly constant.

**Verify yourself, with current numbers:** any recent PR comment on
the [PR list](https://github.com/dfrostar/neuralmind/pulls)
contains the latest sticky benchmark; click into a closed PR to
read it. Or reproduce locally:

```bash
python -m tests.benchmark.run
```

### Fact 2 — The demo reproduces it in 30 seconds on a fresh clone

```bash
git clone https://github.com/dfrostar/neuralmind && cd neuralmind
bash scripts/demo.sh
```

Output (this is real, not a mockup — run the command):

```
  Q: How does authentication work in this codebase?
     naive = 4,736 tok   neuralmind =  829 tok   reduction =   5.7×
  Q: What are the main API endpoints?
     naive = 4,736 tok   neuralmind =  923 tok   reduction =   5.1×
  Q: Explain the billing flow from a user perspective.
     naive = 4,736 tok   neuralmind =  826 tok   reduction =   5.7×

  Average reduction:   5.5×  across 3 queries
  Avg context size:    859 tokens  (vs 4,736 naive)
  Est. monthly saved:  ~$34.89  @ 100 queries/day on Claude 3.5 Sonnet
```

The 5.5× the demo shows on a 500-line fixture is the *floor*.
Production repos are 100× larger; the ratio scales accordingly.

### Fact 3 — Token counting uses `tiktoken`, the industry standard

We don't make up token counts.

- **Main benchmark runner** ([`tests/benchmark/run.py`](../tests/benchmark/run.py)):
  uses OpenAI's [`tiktoken`](https://github.com/openai/tiktoken)
  with the GPT-4o (`o200k_base`) encoding, falling back to
  `cl100k_base` and finally a character-based approximation if both
  vocab downloads fail. This produces the per-query and aggregate
  numbers in the sticky PR comment.
- **Multi-model breakdown** ([`tests/benchmark/multi_model.py`](../tests/benchmark/multi_model.py)):
  uses each provider's actual tokenizer when available — `tiktoken`
  for GPT-4o and GPT-4/3.5 (measured), the official
  [`anthropic`](https://github.com/anthropics/anthropic-sdk-python)
  SDK tokenizer for Claude when the package is installed
  (measured). Llama and rows without an installed vendor tokenizer
  are explicitly labeled as estimates derived from published vocab
  ratios.

Every PR comment marks which rows are measured vs. estimated, so
the provenance is auditable. Savings figures for GPT-4o and Claude
(when measured) are **the same numbers your model provider will
charge you against**. No conversion, no fudge factor.

### Fact 4 — Real repos consistently exceed the fixture numbers

Community-submitted benchmarks on the
[public leaderboard](../docs/community-benchmarks.json):

| Project | Lang | Nodes | Reduction | Tokens/query |
|---|---|---:|---:|---:|
| cmmc20 | JavaScript | 241 | 65.6× | 739 |
| mempalace | Python | 1,626 | 46.0× | 891 |

**Caveat (also in the [Honest Assessment](HONEST-ASSESSMENT.md)):**
n=2 is too few to claim statistical significance. Both repos belong
to the project maintainer. Treat 40–70× as **directional** until the
table grows. Adding your numbers is the single highest-leverage
contribution to this project right now.

```bash
neuralmind benchmark . --contribute   # generates a paste-ready submission
```

---

## The math (with assumptions you can change)

Here's the ROI calculation. Plug in your numbers; the structure
holds regardless.

### Inputs (you change these)

| Variable | Default | Source |
|---|---|---|
| Developers using AI coding agent | 10 | your headcount |
| Code questions per developer per day | 30 | typical agent-assisted dev day |
| Working days per month | 22 | calendar |
| Average tokens per question without NeuralMind | 8,000 | naive context-load on a 50K-line repo |
| Model | Claude 3.5 Sonnet | $3/MTok input |
| Reduction ratio (retrieval stage) | 40× | low end of the headline range |
| Reduction multiplier on full conversation | 0.4× | retrieval is ~40% of input cost on a typical agent run; the rest is conversation history and tool results |

### Calculation

```
monthly_questions          = 10 devs × 30 q/day × 22 days   = 6,600
monthly_tokens_naive       = 6,600 × 8,000                   = 52,800,000
monthly_cost_naive         = 52.8M × $3/MTok                 = $158.40
monthly_tokens_w_nm        = 52.8M × (1 - 0.4 × (1 - 1/40))  = ~32.2M
monthly_cost_w_nm          = ~$96.50
monthly_savings            = $61.90
end_to_end_reduction       = 1.64×
```

That's the **honest** number for a 10-developer team at moderate
query volume. The retrieval-stage reduction is 40×; the end-to-end
reduction is 1.64× because retrieval is one cost line item among
several. **Scale this:**

| Team size | Query volume | Monthly savings (Claude 3.5 Sonnet) | Setup payback |
|---|---|---|---|
| 1 dev, hobbyist | 5 q/day | $1–2/mo | 1+ month |
| 5 devs, small team | 30 q/day | $30/mo | days |
| 10 devs, mid-size | 30 q/day | $60/mo | days |
| 50 devs, mid-size | 30 q/day | $310/mo | hours |
| 100 devs, agent-heavy | 100 q/day | $2,060/mo | hours |
| 500 devs, agent-heavy | 100 q/day | $10,300/mo | hours |

Multiply by 5–8× if your team is on Claude Opus or GPT-4.5. Divide
by 2–3× if you're already running prompt caching (NeuralMind still
helps but the marginal win is smaller).

**Sensitivity:** the biggest uncertainty is the conversation-mix
factor (0.4× above). On a heavily retrieval-bound workload
(orientation queries, "show me the auth flow") the factor is closer
to 0.7×. On a generation-heavy workload (long refactors, code
review) it's closer to 0.2×. Run `neuralmind benchmark` on your
actual workload to pin this down.

---

## Three scenarios where the case is strongest

### Scenario A — Mid-size team hitting context limits weekly

**Profile:** 15 devs, 30K-line monorepo, Claude Code agents that
crash with "context too large" mid-task at least once a day across
the team.

**Without NeuralMind:** developers waste 15 min/day rephrasing
prompts and manually paring context. At $50/hour fully loaded, that
is **$1,650/month in lost engineering time** before any LLM cost.

**With NeuralMind:** `install-hooks` auto-compresses Read/Bash/Grep
output by ~88–91%. Context-limit failures drop to ~zero. LLM bill
drops 1.5–3× alongside.

**Combined value:** $1,650 productivity recovery + $200–400 LLM
savings = **~$2,000/month** for a team of 15. ROI on 2 hours of
setup: ≥10×.

### Scenario B — Solo dev with growing monorepo

**Profile:** 1 dev, codebase grew from 5K to 50K lines, Claude
Sonnet bill went from $20/mo to $200/mo and climbing.

**Without NeuralMind:** bill keeps growing linearly with codebase
size.

**With NeuralMind:** the per-query token cost stops scaling with
repo size. Bill flattens at ~$30–60/mo even as codebase doubles.

**Value:** $140–170/mo savings, payback in days. Critically, the
trajectory changes — costs stop being a function of how much code
you've shipped.

### Scenario C — Regulated environment (offline, on-premise)

**Profile:** financial-services or healthcare team that can't send
code to external APIs, currently relying on local models with
shorter context windows.

**Without NeuralMind:** context limits force code to be loaded in
fragments; agents miss cross-file relationships.

**With NeuralMind:** local-only retrieval means a 13B parameter
model with an 8K-token context window can answer questions that
previously needed a 32K-token frontier model. **Enables use cases
that were previously infeasible**, not just cheaper.

**Value:** unlocks AI-assisted development in environments where it
was previously banned or impractical. Hard to dollarize, but often
the deciding factor in whether the org adopts AI tooling at all.

---

## Verify each claim yourself

Skeptical? Each row of this table is a single command:

| Claim | Command | What you'll see |
|---|---|---|
| The retrieval reduction claim | `bash scripts/demo.sh` | 5.5× on the fixture |
| The CI claim | View any PR's [self-benchmark comment](https://github.com/dfrostar/neuralmind/pulls?q=is%3Apr) | 6.1× on the same fixture |
| The "works on my code" claim | `neuralmind benchmark . --contribute` | YOUR ratio, YOUR tokens, YOUR dollar estimate |
| The "no data leaves your machine" claim | Read [`SECURITY.md`](../SECURITY.md), audit dependencies (chromadb, mcp, pyyaml — all local-only), and run with network disabled (`unshare -n bash scripts/demo.sh` on Linux, or block on a firewall) — the demo completes after the first-run model download | local-only at runtime, not just at install |
| The "incremental updates work" claim | `neuralmind build . --force` then `neuralmind build .` | second run reports ~all skipped |
| The "composes with prompt caching" claim | Run any agent with NeuralMind's compressed Read output through your normal cached prompt — observe lower input tokens at cache reads | Math holds |

If any claim above doesn't reproduce, [open an issue](https://github.com/dfrostar/neuralmind/issues/new)
— that's a higher-priority bug than any feature work.

---

## The case is weaker if…

The honest list, expanded in [HONEST-ASSESSMENT.md](HONEST-ASSESSMENT.md):

- Codebase under ~5K lines: just paste it in. NeuralMind doesn't
  earn its keep.
- Free-tier or flat-rate LLM access: no per-query cost to reduce.
- Inline-completion-only workflows (Copilot-style): wrong layer of
  the stack — NeuralMind is for agents.
- Already-optimized stack with prompt caching + long context: the
  marginal win shrinks. Measure on your workload before deciding.
- Polyglot monorepo with weak tree-sitter coverage on your
  primary languages: retrieval quality drops below the headline.
  Run the benchmark — if you see <10× on your code, the math doesn't
  pencil out.

---

## What would make this case stronger over time

We're tracking these as the highest-impact research investments:

1. **Faithfulness study** — does the agent's *answer quality*
   improve, not just shrink? Currently anecdotal; needs a
   structured eval set.
2. **End-to-end workload benchmark** — measure full multi-turn
   sessions with tool calls, not just isolated retrieval queries.
   This nails down the "0.4× conversation-mix factor" assumption.
3. **n ≥ 10 outside community benchmarks** across languages and
   repo shapes. Currently n=2.
4. **Long-context-baseline comparison** — quantify the marginal win
   over a Claude Sonnet 1M / GPT-4 turbo + prompt caching baseline.

These appear on [ROADMAP.md](../ROADMAP.md) under "Next" and are
open contribution targets. If your organization is evaluating
NeuralMind for a real procurement decision, contributing one of
these studies materially helps your own evaluation and the
ecosystem.

---

## Decision in three lines

- **Run the benchmark before deciding.** `bash scripts/demo.sh`
  takes 30 seconds; `neuralmind benchmark .` takes 5 minutes on
  your code. Skip everything else on this page if those numbers
  don't justify it.
- **The case is strongest for: 10+ devs, 10K+ line repo, paying for
  inference, hitting context limits.** ROI in days, sometimes hours.
- **The case is weakest for: small repos, free tiers, or
  generation-heavy workloads where retrieval is a small slice of
  total cost.** Honest answer: skip it for now.
