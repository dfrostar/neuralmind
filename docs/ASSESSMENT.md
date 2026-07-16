# The free AI-spend assessment — what to expect

A working session, not a sales call. We measure NeuralMind's actual
token-reduction ratio on one of your repos and hand you a spend model
built from your numbers — whether or not you deploy anything.

**Book it:** [hello@neuralmind.uk](mailto:hello@neuralmind.uk?subject=Free%20AI-spend%20assessment)

---

## Fastest path: run it yourself in 5 minutes

You don't need to wait for a call. The assessment's core measurement
is a command you can run right now, on your own hardware, with
nothing leaving your machine:

```bash
pip install neuralmind
neuralmind build .          # index your repo locally
neuralmind benchmark .      # → your measured reduction ratio + cost estimate
```

Email the benchmark output to
[hello@neuralmind.uk](mailto:hello@neuralmind.uk?subject=Self-serve%20assessment%20results)
along with three numbers — engineer count, monthly API spend, and
GPU fleet if you run one — and we'll send back the full three-line
spend model in your numbers. You share only the report; your code
stays where it is.

---

## What you get

1. **A measured reduction ratio on your code.** We run
   `neuralmind benchmark` against a repo you choose (on your
   hardware if you prefer — nothing needs to leave your machines).
   The output is per-query input-token counts vs. a naive baseline,
   the same methodology as our [public CI benchmark](BUSINESS-CASE.md).
2. **A three-line spend model in your numbers.** Per-seat
   subscriptions, usage-based API spend (direct, OpenRouter,
   Bedrock, Vertex), and self-hosted GPU capacity — modeled
   separately, with the assumptions written down so your finance
   team can change them. Structure documented in
   [BUSINESS-CASE.md](BUSINESS-CASE.md#your-full-ai-spend-the-three-budget-lines).
3. **An honest fit verdict.** If your workload is generation-heavy,
   your repos are small, or prompt caching already covers you, the
   model will say so. The methodology's failure modes are public:
   [The case is weaker if…](BUSINESS-CASE.md#the-case-is-weaker-if)

## What we'll ask — have this ready

The model is only as good as its inputs. The call goes fastest when
you bring:

**Team & tools**
- How many engineers use AI coding tools, and which ones
- Seat prices and whether your plan has usage tiers or overage charges

**API / usage-based spend**
- Last 3 months of invoices from each provider (OpenRouter,
  Anthropic, OpenAI, Bedrock, Vertex — whatever you use)
- Input-vs-output token split if your dashboard shows it
- Rough share of traffic that's code questions / agent retrieval
  vs. other workloads
- Whether prompt caching is enabled

**Self-hosted inference (if applicable)**
- GPU types and count (e.g. H100s), and your contracted
  $/GPU-hour or amortized cost
- Fleet utilization, and prefill-vs-decode share if you've
  profiled it
- Queries/day served and typical context length

**Workload shape**
- Size of the repo(s) you'd point NeuralMind at
- Code questions per engineer per day, roughly

Don't have all of it? Come anyway — we'll model with stated
assumptions and mark every estimated input as estimated.

## What we won't do

- Upload your code anywhere. The benchmark runs locally; you can
  run it yourself and just share the output.
- Quote savings we didn't measure. Measured numbers are labeled
  measured; derived numbers are labeled derived, same as
  [everywhere else in this project](BUSINESS-CASE.md).

---

*The software is MIT-licensed and free. If the assessment numbers
justify going further, the paid engagements — fixed-fee pilot,
support & assurance subscription — are described in
[OFFERINGS.md](OFFERINGS.md).*
