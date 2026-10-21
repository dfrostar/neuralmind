# NeuralMind vs. Long context windows (Claude 1M, Gemini 2M, Projects)

## The premise

"Why not just stuff the whole codebase into a 1M or 2M context window?"

It works — for a while. Then the bill arrives.

## The numbers

Take `psf/requests`, the smallest repo on NeuralMind's
[public benchmark](https://github.com/dfrostar/neuralmind/blob/main/docs/benchmarks/public.md)
(v4.12.0), at 100 queries/day. Token counts are measured; the dollar column is
arithmetic at $3/MTok input, not a measurement of anyone's bill.

| Approach | Tokens per query | Monthly input cost (Claude Sonnet) |
|---|---|---|
| Every source file every turn | 41,729 | ~$376 |
| NeuralMind query | 816 (mean) | ~$7 |

On the largest repo, `rich`, pasting every source file is 232,483 tokens per
query — more than a 200K-token window holds — against 961 for NeuralMind.

Long context windows make it *possible* to stuff everything in. They do not make it *cheap*. Input tokens are billed per token — a 1M context at $3/MTok is $3 per message.

## Other dimensions

| Dimension | Long context | NeuralMind |
|---|---|---|
| Cost scaling | Linear in codebase size | Roughly flat (670–961 mean tokens per question across repos of 41,729–232,483 tokens) |
| Recall quality | Strong on small repos, degrades on large ones (needle-in-haystack effects) | Measured: gold file on 40 of 40 public-benchmark queries; 93.3% top-five on the 150-question retrieval eval, which misses 10 |
| Latency | Increases with context size | Roughly flat |
| Provider lock-in | Ties you to 1M+ models | Model-agnostic |
| Works offline | No | Yes |
| Prompt caching savings | Possible, but full repo still loaded | Context is small enough that caching is secondary |

## When to pick which

- **Use raw long context** for one-off exploration on small repos where you don't mind the bill.
- **Use NeuralMind** for sustained coding work — the per-query savings add up daily, and the per-question token cost stays roughly flat as the repo grows, where raw long context grows with it.

The two also compose: feed NeuralMind's output into a long-context model and you get both focus and headroom.

---

[← Back to comparison index](./README.md)
